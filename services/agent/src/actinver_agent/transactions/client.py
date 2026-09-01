"""HTTP client for transaction-service. Typed errors are re-raised from the
RFC 9457 ``code`` so the BFF renders them identically to the in-process path."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import structlog

from actinver_agent.graph.state import FormSpec
from actinver_agent.ports import OrderReceipt, StepUpChallenge
from actinver_agent.transactions import errors as txerr

log = structlog.get_logger(__name__)


class HttpTransactions:
    def __init__(self, base_url: str, http: httpx.AsyncClient, *, timeout_s: float = 5.0) -> None:
        self._base = base_url.rstrip("/")
        self._http = http
        self._timeout = timeout_s

    async def _post(
        self, path: str, body: dict[str, Any], headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._http.post(
                f"{self._base}{path}", json=body, headers=headers, timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            log.error("transaction.unavailable", path=path, error=type(exc).__name__)
            raise txerr.ExecutionUnavailable() from exc
        if response.status_code >= 400:
            try:
                problem = response.json()
            except ValueError:
                problem = {}
            code = str(problem.get("code", "SERVICE_UNAVAILABLE"))
            raise txerr.ERROR_BY_CODE.get(code, txerr.ExecutionUnavailable)(problem.get("detail"))
        data: dict[str, Any] = response.json()
        return data

    async def issue_challenge(
        self, *, client_id: str, form_id: str, amount_hash: str
    ) -> StepUpChallenge:
        data = await self._post(
            "/v1/step-up/challenge",
            {"client_id": client_id, "form_id": form_id, "amount_hash": amount_hash},
        )
        return StepUpChallenge(
            challenge_id=str(data["challenge_id"]),
            challenge=str(data["challenge"]),
            expires_at=datetime.fromisoformat(str(data["expires_at"])),
        )

    async def execute(
        self,
        *,
        client_id: str,
        form_spec: FormSpec,
        values: dict[str, Any],
        acknowledgements: list[str],
        step_up_assertion: str,
        challenge_id: str,
        idempotency_key: str,
        suitability_verdict_id: str | None,
        jkt: str | None = None,
        device_id: str | None = None,
    ) -> OrderReceipt:
        data = await self._post(
            "/v1/orders",
            {
                "client_id": client_id,
                "form_spec": form_spec.model_dump(mode="json"),
                "values": values,
                "acknowledgements": acknowledgements,
                "step_up_assertion": step_up_assertion,
                "challenge_id": challenge_id,
                "suitability_verdict_id": suitability_verdict_id,
                "jkt": jkt,
                "device_id": device_id,
            },
            headers={"Idempotency-Key": idempotency_key},
        )
        return OrderReceipt(
            order_id=str(data["order_id"]),
            status=str(data["status"]),
            settlement_date=str(data["settlement_date"]),
            evidence_id=data.get("evidence_id"),
            idempotent_replay=bool(data.get("idempotent_replay", False)),
        )

    async def health(self) -> bool:
        try:
            response = await self._http.get(f"{self._base}/readyz", timeout=self._timeout)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
