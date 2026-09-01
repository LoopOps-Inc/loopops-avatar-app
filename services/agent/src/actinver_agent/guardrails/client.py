"""HTTP client for the separately deployed guardrail-service. Fail-closed."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from actinver_agent.graph.state import GuardrailVerdict
from actinver_agent.ports import OutputCheckRequest

log = structlog.get_logger(__name__)


class GuardrailUnavailable(RuntimeError):
    """The guardrail could not be reached. No response may be emitted."""


class HttpGuardrail:
    def __init__(self, base_url: str, http: httpx.AsyncClient, *, timeout_s: float = 2.0) -> None:
        self._base = base_url.rstrip("/")
        self._http = http
        self._timeout = timeout_s

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._http.post(
                f"{self._base}{path}", json=body, timeout=self._timeout
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data
        except (httpx.HTTPError, ValueError) as exc:
            log.error("guardrail.unavailable", path=path, error=type(exc).__name__)
            raise GuardrailUnavailable(path) from exc

    async def check_input(
        self, *, text: str, transcript_confidence: float | None
    ) -> tuple[GuardrailVerdict, str]:
        data = await self._post(
            "/v1/guardrail/input",
            {"text": text, "transcript_confidence": transcript_confidence},
        )
        return GuardrailVerdict.model_validate(data["verdict"]), str(data["redacted_text"])

    async def scan_retrieved(self, *, text: str) -> bool:
        data = await self._post("/v1/guardrail/scan", {"text": text})
        return bool(data["injection"])

    async def check_output(self, request: OutputCheckRequest) -> GuardrailVerdict:
        data = await self._post(
            "/v1/guardrail/output",
            {
                "speech": request.speech,
                "intent": str(request.intent) if request.intent else None,
                "locale": request.locale,
                "register": request.register,
                "provenance_keys": sorted(request.provenance_keys),
                "stripped_product_terms": list(request.stripped_product_terms),
                "rewrite_attempts": request.rewrite_attempts,
                "max_rewrite_attempts": request.max_rewrite_attempts,
                "sentence_mode": request.sentence_mode,
            },
        )
        return GuardrailVerdict.model_validate(data)

    async def disclosure_texts(self, ids: list[str]) -> dict[str, tuple[str, str]]:
        try:
            response = await self._http.get(
                f"{self._base}/v1/guardrail/disclosures",
                params={"ids": ",".join(ids)},
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GuardrailUnavailable("disclosures") from exc
        return {k: (v["text"], v["version"]) for k, v in data["items"].items()}

    async def health(self) -> bool:
        try:
            response = await self._http.get(f"{self._base}/readyz", timeout=self._timeout)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
