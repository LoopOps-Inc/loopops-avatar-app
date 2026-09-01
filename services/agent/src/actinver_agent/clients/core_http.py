"""mTLS client for the Actinver core (positions, profiles, products, orders).

Contract-first: the paths and response shapes below are the agreed interface
with the platform team pending the core-API inventory (README §6 item 1). Every
method is read-only, takes ``client_id`` as an injected argument and returns a
schema-validated payload carrying ``as_of``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from actinver_agent.clients.http_base import JsonClient, mtls_context
from actinver_agent.config import Settings


class _Envelope(BaseModel):
    """Core responses are envelopes ``{"as_of": ..., "data": {...}}``."""

    model_config = ConfigDict(extra="forbid")

    as_of: str
    data: dict[str, Any]

    def flat(self) -> dict[str, Any]:
        return {"as_of": self.as_of, **self.data}


class _Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limits: dict[str, float]


class CoreBankingHttp:
    """Implements ``CoreBankingPort`` over mTLS with its own connection pool."""

    def __init__(self, settings: Settings) -> None:
        self._client = JsonClient(
            name="core-banking",
            base_url=settings.core_api_base_url,
            timeout_s=settings.limits.tool_timeout_s,
            verify=mtls_context(
                settings.core_api_mtls_cert_path,
                settings.core_api_mtls_key_path,
                settings.core_api_ca_path,
            ),
            max_connections=32,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        env = await self._client.get_model(
            path, _Envelope, params={k: v for k, v in params.items() if v is not None}
        )
        return env.flat()

    async def get_client_context(self, *, client_id: str) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/context")

    async def get_investor_profile(self, *, client_id: str) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/investor-profile")

    async def get_positions(self, *, client_id: str) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/positions")

    async def get_performance(self, *, client_id: str, period: str) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/performance", period=period)

    async def get_attribution(
        self, *, client_id: str, period: str, granularity: str
    ) -> dict[str, Any]:
        return await self._get(
            f"/clients/{client_id}/attribution", period=period, granularity=granularity
        )

    async def get_cash_balance(self, *, client_id: str) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/cash")

    async def get_accounts(self, *, client_id: str) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/accounts")

    async def get_transaction_history(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/operations", **kw)

    async def get_statement(self, *, client_id: str, year: int, month: int) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/statements/{year}/{month:02d}")

    async def search_products(self, **filters: Any) -> dict[str, Any]:
        return await self._get(
            "/products",
            **{k: (",".join(v) if isinstance(v, list) else v) for k, v in filters.items()},
        )

    async def get_product_detail(self, *, product_id: str) -> dict[str, Any]:
        return await self._get(f"/products/{product_id}")

    async def get_product_profile(self, *, product_id: str) -> dict[str, Any]:
        return await self._get(f"/products/{product_id}/committee-profile")

    async def compare_products(self, *, product_ids: list[str]) -> dict[str, Any]:
        return await self._get("/products/compare", ids=",".join(product_ids))

    async def get_diversification_limits(self) -> dict[str, float]:
        result = await self._client.get_model("/committee/diversification-limits", _Limits)
        return result.limits

    async def get_transaction_requirements(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/transaction-requirements", **kw)

    async def simulate_investment(self, **kw: Any) -> dict[str, Any]:
        return await self._get("/simulations", **kw)

    async def calculate_fees_and_taxes(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        return await self._get(f"/clients/{client_id}/fees", **kw)

    async def get_device_public_key(self, *, client_id: str, device_id: str) -> str | None:
        data = await self._get(f"/clients/{client_id}/devices/{device_id}/public-key")
        key = data.get("public_key_jwk")
        return None if key is None else str(key)

    async def health(self) -> bool:
        return await self._client.health()
