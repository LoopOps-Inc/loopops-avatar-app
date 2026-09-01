"""guardrail-service: input and output filters as a separately deployed,
fail-closed dependency (docs/04-backend/01 §2). Owned by Compliance."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query
from pydantic import BaseModel, ConfigDict, Field

from actinver_agent.graph.state import GuardrailVerdict, Intent
from actinver_agent.guardrails.disclosures import load_disclosures
from actinver_agent.guardrails.dlp import export_dlp_ruleset
from actinver_agent.guardrails.engine import GuardrailEngine
from actinver_agent.ports import OutputCheckRequest


class InputRequest(BaseModel):
    text: str = Field(max_length=20_000)
    transcript_confidence: float | None = None


class InputResponse(BaseModel):
    verdict: GuardrailVerdict
    redacted_text: str


class ScanRequest(BaseModel):
    text: str = Field(max_length=200_000)


class ScanResponse(BaseModel):
    injection: bool


class OutputRequest(BaseModel):
    speech: str = Field(max_length=20_000)
    intent: str | None = None
    locale: str = "es-MX"
    speech_register: str = Field(default="tu", alias="register")
    model_config = ConfigDict(populate_by_name=True)
    provenance_keys: list[str] = Field(default_factory=list)
    stripped_product_terms: list[str] = Field(default_factory=list)
    rewrite_attempts: int = 0
    max_rewrite_attempts: int = 2
    sentence_mode: bool = False


class DisclosureItem(BaseModel):
    text: str
    version: str


class DisclosuresResponse(BaseModel):
    items: dict[str, DisclosureItem]


def create_app(*, prompts_dir: str = "prompts", min_confidence: float = 0.60) -> FastAPI:
    catalogue = load_disclosures(prompts_dir)
    engine = GuardrailEngine(catalogue)
    app = FastAPI(title="Actinver AI Advisor - guardrail-service", version="0.1.0")

    @app.post("/v1/guardrail/input", response_model=InputResponse)
    async def check_input(body: InputRequest) -> InputResponse:
        result = engine.check_input(
            body.text,
            transcript_confidence=body.transcript_confidence,
            min_confidence=min_confidence,
        )
        return InputResponse(verdict=result.verdict, redacted_text=result.redacted_text)

    @app.post("/v1/guardrail/scan", response_model=ScanResponse)
    async def scan(body: ScanRequest) -> ScanResponse:
        return ScanResponse(injection=engine.scan_retrieved(body.text))

    @app.post("/v1/guardrail/output", response_model=GuardrailVerdict)
    async def check_output(body: OutputRequest) -> GuardrailVerdict:
        intent = Intent(body.intent) if body.intent else None
        return engine.check_output(
            OutputCheckRequest(
                speech=body.speech,
                intent=intent,
                locale=body.locale,
                register=body.speech_register,
                provenance_keys=frozenset(body.provenance_keys),
                stripped_product_terms=tuple(body.stripped_product_terms),
                rewrite_attempts=body.rewrite_attempts,
                max_rewrite_attempts=body.max_rewrite_attempts,
                sentence_mode=body.sentence_mode,
            )
        )

    @app.get("/v1/guardrail/disclosures", response_model=DisclosuresResponse)
    async def disclosures(ids: str = Query(default="")) -> DisclosuresResponse:
        wanted = [i for i in ids.split(",") if i] or catalogue.ids()
        return DisclosuresResponse(
            items={
                k: DisclosureItem(text=t, version=v)
                for k, (t, v) in catalogue.texts(wanted).items()
            }
        )

    @app.get("/v1/guardrail/dlp-ruleset")
    async def dlp_ruleset() -> dict[str, Any]:
        return export_dlp_ruleset()

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, Any]:
        return {"ready": True, "checks": {"disclosures": len(catalogue.ids()) > 0}}

    return app


def app() -> FastAPI:
    """uvicorn factory (``serve --role guardrail``)."""
    from actinver_agent.config import get_settings

    settings = get_settings()
    return create_app(
        prompts_dir=settings.prompts_dir, min_confidence=settings.voice.stt_min_confidence
    )
