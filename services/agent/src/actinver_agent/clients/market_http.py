"""Licensed market data vendor (quotes, indices, FX, CETES/TIIE, calendar).

Prices come from the licensed vendor, never from scraping. Symbols only leave
the perimeter (docs/01-architecture/02 §5).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from actinver_agent.clients.http_base import JsonClient
from actinver_agent.config import Settings


class _QuotesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: str
    quotes: list[dict[str, Any]]


class _CalendarResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: str
    events: list[dict[str, Any]]


class MarketDataHttp:
    def __init__(self, settings: Settings, api_key: str | None = None) -> None:
        self._client = JsonClient(
            name="market-data",
            base_url=settings.market_data_base_url,
            timeout_s=settings.limits.tool_timeout_s,
            headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
            max_connections=16,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_quotes(self, *, symbols: list[str]) -> dict[str, Any]:
        result = await self._client.get_model(
            "/quotes", _QuotesResponse, params={"symbols": ",".join(symbols)}
        )
        return result.model_dump()

    async def get_calendar(self, **kw: Any) -> dict[str, Any]:
        params = {
            k: (",".join(v) if isinstance(v, list) else v) for k, v in kw.items() if v is not None
        }
        result = await self._client.get_model("/calendar", _CalendarResponse, params=params)
        return result.model_dump()

    async def health(self) -> bool:
        return await self._client.health()
