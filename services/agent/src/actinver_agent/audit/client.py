"""HTTP client for audit-service."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from actinver_agent.audit.sink import EvidenceUnavailable
from actinver_agent.ports import EvidenceWriteResult

log = structlog.get_logger(__name__)


class HttpAudit:
    def __init__(self, base_url: str, http: httpx.AsyncClient, *, timeout_s: float = 3.0) -> None:
        self._base = base_url.rstrip("/")
        self._http = http
        self._timeout = timeout_s

    async def write(self, *, record: dict[str, Any], fail_closed: bool) -> EvidenceWriteResult:
        try:
            response = await self._http.post(
                f"{self._base}/v1/evidence",
                json={"record": record, "fail_closed": fail_closed},
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.error("audit.unavailable", fail_closed=fail_closed, error=type(exc).__name__)
            # The remote service already spools informational records itself; if
            # it is unreachable altogether there is nowhere to spool, so every
            # write is fail-closed at this point.
            raise EvidenceUnavailable(record.get("evidence_id", "")) from exc
        return EvidenceWriteResult(
            evidence_id=str(data["evidence_id"]),
            content_hash=data.get("content_hash"),
            spooled=bool(data.get("spooled", False)),
        )

    async def verify_thread(self, thread_id: str) -> tuple[bool, int, str | None]:
        response = await self._http.get(
            f"{self._base}/v1/evidence/verify/{thread_id}", timeout=self._timeout * 5
        )
        response.raise_for_status()
        data = response.json()
        return (
            bool(data["ok"]),
            int(data.get("records", 0)),
            data.get("first_divergent_evidence_id"),
        )

    async def health(self) -> bool:
        try:
            response = await self._http.get(f"{self._base}/readyz", timeout=self._timeout)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
