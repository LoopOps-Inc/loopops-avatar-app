"""HTTP client for suitability-service. Fail-closed: no verdict, no advice."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from actinver_agent.graph.state import InvestorProfile, ProductProfile, SuitabilityReport
from actinver_agent.ports import EvaluationInput

log = structlog.get_logger(__name__)


class SuitabilityUnavailable(RuntimeError):
    pass


class HttpSuitability:
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
            log.error("suitability.unavailable", path=path, error=type(exc).__name__)
            raise SuitabilityUnavailable(path) from exc

    async def evaluate(
        self,
        *,
        client_id: str,
        profile: InvestorProfile,
        products: list[ProductProfile],
        ctx: EvaluationInput,
    ) -> SuitabilityReport:
        data = await self._post(
            "/v1/suitability/evaluate",
            {
                "client_id": client_id,
                "profile": profile.model_dump(mode="json"),
                "products": [p.model_dump(mode="json") for p in products],
                "context": {
                    "today": ctx.today.isoformat(),
                    "amount": str(ctx.amount),
                    "portfolio_total": str(ctx.portfolio_total),
                    "current_weight_by_product": ctx.current_weight_by_product,
                    "current_weight_by_asset_class": ctx.current_weight_by_asset_class,
                    "liquid_pct": ctx.liquid_pct,
                    "diversification_limits": ctx.diversification_limits,
                },
            },
        )
        return SuitabilityReport.model_validate(data)

    async def verify(self, *, report: SuitabilityReport) -> bool:
        data = await self._post("/v1/suitability/verify", report.model_dump(mode="json"))
        return bool(data["valid"])

    async def health(self) -> bool:
        try:
            response = await self._http.get(f"{self._base}/readyz", timeout=self._timeout)
            return response.status_code == 200
        except httpx.HTTPError:
            return False
