"""Gemini bindings through the google-genai SDK (ADR-0003).

Production uses Vertex AI (``vertexai=True`` with workload identity); an AI
Studio key is accepted for local development only (``Settings.validate_posture``
refuses it elsewhere).

Every request body is serialised, passed through the redaction proxy, and only
then handed to the SDK. The system prompt must be clean (it carries first name
and profile bands only); a hit there is a pipeline defect and raises.

Structured outputs: the router uses a JSON response schema; the planner uses
function declarations; the generator streams narrative text and then extracts
candidate product ids from a trailing ``<candidatos>[...]</candidatos>`` block
requested in the task prompt (no second call, no extra latency).
"""

from __future__ import annotations

import re
import time
from typing import Any

import orjson
import structlog
from google import genai
from google.genai import types
from pydantic import BaseModel

from actinver_agent.config import Settings
from actinver_agent.graph.state import AdvisorState, Intent
from actinver_agent.llm.redaction import RedactionProxy
from actinver_agent.ports import ClassificationResult, GenerationResult, ToolCall

log = structlog.get_logger(__name__)

_CANDIDATES_RE = re.compile(r"<candidatos>(?P<body>.*?)</candidatos>", re.DOTALL)
_AMOUNT_RE = re.compile(r"<monto>(?P<body>[\d.]+)</monto>")


class GeminiClientFactory:
    def __init__(self, settings: Settings, api_key: str | None = None) -> None:
        self._settings = settings
        self._api_key = api_key
        self._client: genai.Client | None = None

    def client(self) -> genai.Client:
        if self._client is None:
            if self._settings.llm.provider == "vertex":
                self._client = genai.Client(
                    vertexai=True,
                    project=self._settings.vertex.project_id,
                    location=self._settings.vertex.location,
                )
            else:
                if not self._api_key:
                    raise RuntimeError("LLM_PROVIDER=gemini_api requires a resolved API key")
                self._client = genai.Client(api_key=self._api_key)
        return self._client

    @property
    def provider(self) -> str:
        return "vertex-ai" if self._settings.llm.provider == "vertex" else "gemini-api"


class _RouterOutput(BaseModel):
    intent: Intent
    confidence: float
    runner_up: Intent | None = None
    profile_filtered: bool = False


def _thinking_config(model: str) -> types.ThinkingConfig | None:
    """Router and planner are structured-output calls: no visible reasoning.

    Gemini 2.5 Flash spends the output budget on thinking unless told not to,
    which truncated the router JSON. Pro models cannot disable thinking, so the
    budget is left to the model there.
    """
    return types.ThinkingConfig(thinking_budget=0) if "flash" in model.lower() else None


def _redacted(proxy: RedactionProxy, payload: dict[str, Any]) -> dict[str, Any]:
    body, _count = proxy.redact_body(orjson.dumps(payload, default=str))
    result: dict[str, Any] = orjson.loads(body)
    return result


class GeminiClassifier:
    def __init__(
        self, factory: GeminiClientFactory, settings: Settings, router_prompt: str
    ) -> None:
        self._factory = factory
        self._settings = settings
        self._router_prompt = router_prompt
        self._proxy = RedactionProxy()

    async def classify(self, *, text: str, history: list[str], locale: str) -> ClassificationResult:
        payload = _redacted(
            self._proxy,
            {
                "history": history[-6:],
                "text": text,
                "locale": locale,
            },
        )
        contents = (
            "Historial reciente:\n"
            + "\n".join(f"- {h}" for h in payload["history"])
            + f"\n\nMensaje del cliente ({payload['locale']}): {payload['text']}"
        )
        config = types.GenerateContentConfig(
            system_instruction=self._router_prompt,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=_RouterOutput,
            max_output_tokens=256,
            thinking_config=_thinking_config(self._settings.vertex.model_fast),
            http_options=types.HttpOptions(timeout=int(self._settings.vertex.timeout_s * 1000)),
        )
        response = await self._factory.client().aio.models.generate_content(
            model=self._settings.vertex.model_fast,
            contents=contents,
            config=config,
        )
        parsed = _RouterOutput.model_validate_json(response.text or "{}")
        usage = response.usage_metadata
        return ClassificationResult(
            intent=parsed.intent,
            confidence=max(0.0, min(1.0, parsed.confidence)),
            runner_up=parsed.runner_up,
            profile_filtered=parsed.profile_filtered or parsed.intent is Intent.ADVISORY_RECOMMEND,
            model=self._settings.vertex.model_fast,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
        )


class GeminiPlanner:
    def __init__(self, factory: GeminiClientFactory, settings: Settings, plan_prompt: str) -> None:
        self._factory = factory
        self._settings = settings
        self._plan_prompt = plan_prompt
        self._proxy = RedactionProxy()

    async def plan(
        self, *, state: AdvisorState, declarations: list[dict[str, Any]]
    ) -> list[ToolCall]:
        if not declarations:
            return []
        payload = _redacted(
            self._proxy,
            {
                "text": state.get("client_input_text", ""),
                "intent": str(state.get("intent", "")),
                "declarations": declarations,
            },
        )
        tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=d["name"],
                        description=d["description"],
                        parameters=_schema(d["parameters"]),
                    )
                    for d in payload["declarations"]
                ]
            )
        ]
        config = types.GenerateContentConfig(
            system_instruction=self._plan_prompt,
            temperature=0.0,
            tools=tools,
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            ),
            thinking_config=_thinking_config(self._settings.vertex.model_fast),
            http_options=types.HttpOptions(timeout=int(self._settings.vertex.timeout_s * 1000)),
        )
        response = await self._factory.client().aio.models.generate_content(
            model=self._settings.vertex.model_fast,
            contents=f"Intención: {payload['intent']}\nMensaje: {payload['text']}",
            config=config,
        )
        calls: list[ToolCall] = []
        allowed = {d["name"] for d in declarations}
        for candidate in response.candidates or []:
            for part in (candidate.content.parts if candidate.content else []) or []:
                fc = getattr(part, "function_call", None)
                if fc is not None and fc.name in allowed:
                    calls.append(ToolCall(fc.name, dict(fc.args or {})))
        return calls[:10]


class GeminiGenerator:
    def __init__(self, factory: GeminiClientFactory, settings: Settings) -> None:
        self._factory = factory
        self._settings = settings
        self._proxy = RedactionProxy()

    async def generate(
        self,
        *,
        state: AdvisorState,
        system_prompt: str,
        model: str,
        max_tokens: int,
        rewrite_hint: str | None,
    ) -> GenerationResult:
        # The system prompt carries first name and bands only. Anything else
        # reaching this point is a defect upstream; refuse rather than redact.
        self._proxy.assert_clean(system_prompt, field="system_instruction")

        tool_context = {
            name: result.data for name, result in state.get("tool_results", {}).items() if result.ok
        }
        history = [
            {"role": "user" if m.type == "human" else "model", "text": str(m.content)}
            for m in state.get("messages", [])[-10:]
        ]
        payload = _redacted(
            self._proxy,
            {
                "history": history,
                "tool_results": tool_context,
                "rewrite_hint": rewrite_hint,
            },
        )
        # Absolute position values go to the UI directly; the model sees what
        # the redaction proxy let through, and the composer never trusts a
        # figure the model repeats unless it exists in the provenance map.
        contents: list[types.Content] = [
            types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"])])
            for h in payload["history"][:-1]
        ]
        last = (
            payload["history"][-1]["text"]
            if payload["history"]
            else state.get("client_input_text", "")
        )
        tool_block = orjson.dumps(payload["tool_results"], default=str).decode()
        user_text = (
            f"{last}\n\n<resultados_de_herramientas>\n{tool_block}\n</resultados_de_herramientas>"
        )
        if payload["rewrite_hint"]:
            user_text += f"\n\nINSTRUCCIÓN DEL SISTEMA: {payload['rewrite_hint']}"
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_text)]))

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self._settings.vertex.temperature,
            top_p=self._settings.vertex.top_p,
            seed=self._settings.vertex.seed,
            max_output_tokens=max_tokens,
            http_options=types.HttpOptions(timeout=int(self._settings.vertex.timeout_s * 1000)),
        )
        started = time.perf_counter()
        ttft_ms = 0
        chunks: list[str] = []
        usage: Any = None
        blocked = False
        stream = await self._factory.client().aio.models.generate_content_stream(
            model=model,
            contents=contents,
            config=config,
        )
        async for chunk in stream:
            if chunk.text:
                if not chunks:
                    ttft_ms = int((time.perf_counter() - started) * 1000)
                chunks.append(chunk.text)
            if chunk.usage_metadata is not None:
                usage = chunk.usage_metadata
            feedback = getattr(chunk, "prompt_feedback", None)
            if feedback is not None and getattr(feedback, "block_reason", None):
                blocked = True
        raw = "".join(chunks)
        speech, candidates, amount = _split_structured(raw)
        return GenerationResult(
            speech=speech,
            candidate_product_ids=candidates,
            proposed_amount=amount,
            model=model,
            provider=self._factory.provider,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
            ttft_ms=ttft_ms,
            safety_blocked=blocked,
        )


class GeminiEmbedder:
    def __init__(self, factory: GeminiClientFactory, model: str = "gemini-embedding-001") -> None:
        self._factory = factory
        self._model = model
        self._proxy = RedactionProxy()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # No client data is ever embedded (ADR-0014); redaction is a belt-and-braces check.
        clean = [self._proxy.redact_body(t)[0] for t in texts]
        response = await self._factory.client().aio.models.embed_content(
            model=self._model,
            contents=clean,
            config=types.EmbedContentConfig(output_dimensionality=768),
        )
        return [list(e.values or []) for e in (response.embeddings or [])]


def _schema(parameters: dict[str, Any]) -> dict[str, Any]:
    """Gemini accepts a subset of JSON Schema; strip what it rejects."""
    allowed = {
        "type",
        "properties",
        "required",
        "description",
        "enum",
        "items",
        "format",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "default",
        "anyOf",
        "nullable",
    }

    def clean(node: Any) -> Any:
        if isinstance(node, dict):
            out = {k: clean(v) for k, v in node.items() if k in allowed and k != "properties"}
            if isinstance(node.get("properties"), dict):
                # Keys under "properties" are property names, not schema keywords.
                out["properties"] = {name: clean(sub) for name, sub in node["properties"].items()}
            if "anyOf" in out:
                variants = [v for v in out["anyOf"] if v.get("type") != "null"]
                if len(variants) == 1:
                    out = {
                        **variants[0],
                        "nullable": True,
                        **{k: v for k, v in out.items() if k not in {"anyOf"}},
                    }
                    out.pop("anyOf", None)
            return out
        if isinstance(node, list):
            return [clean(v) for v in node]
        return node

    result: dict[str, Any] = clean(parameters)
    result.setdefault("type", "object")
    return result


def _split_structured(raw: str) -> tuple[str, list[str], Any]:
    from decimal import Decimal, InvalidOperation

    candidates: list[str] = []
    amount = None
    match = _CANDIDATES_RE.search(raw)
    if match:
        try:
            parsed = orjson.loads(match.group("body"))
            candidates = [str(p) for p in parsed if isinstance(p, str)][:4]
        except orjson.JSONDecodeError:
            candidates = []
        raw = raw[: match.start()] + raw[match.end() :]
    amount_match = _AMOUNT_RE.search(raw)
    if amount_match:
        try:
            amount = Decimal(amount_match.group("body"))
        except InvalidOperation:
            amount = None
        raw = raw[: amount_match.start()] + raw[amount_match.end() :]
    return raw.strip(), candidates, amount
