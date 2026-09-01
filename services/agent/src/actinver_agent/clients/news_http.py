"""News retrieval over an explicit host allow-list, and the research corpus.

Retrieved text is untrusted: the tool layer wraps it, the guardrail scans it,
and the model is told the block is data, never instruction
(docs/04-backend/03 §3). The allow-list has no wildcards; adding a host is a
change request (infra/terraform/egress-allowlist.tf).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import structlog
from pydantic import BaseModel, ConfigDict

from actinver_agent.clients.http_base import JsonClient
from actinver_agent.config import Settings

log = structlog.get_logger(__name__)


class _Items(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: str
    items: list[dict[str, Any]]


class NewsHttp:
    def __init__(self, settings: Settings, *, search_base_url: str, research_base_url: str) -> None:
        if any("*" in host for host in settings.news_allowlist):
            raise ValueError("wildcards are not permitted in the news allow-list")
        self._allow = frozenset(h.lower() for h in settings.news_allowlist)
        self._search = JsonClient(
            name="news-search",
            base_url=search_base_url,
            timeout_s=settings.limits.tool_timeout_s,
            max_connections=8,
        )
        self._research = JsonClient(
            name="actinver-research",
            base_url=research_base_url,
            timeout_s=settings.limits.tool_timeout_s,
            max_connections=8,
        )

    async def aclose(self) -> None:
        await self._search.aclose()
        await self._research.aclose()

    def _allowed(self, item: dict[str, Any]) -> bool:
        host = (urlparse(str(item.get("url", ""))).hostname or "").lower()
        host = host.removeprefix("www.")
        if host in self._allow:
            return True
        log.warning("news.host_not_allowlisted", host=host)
        return False

    async def search(self, **kw: Any) -> dict[str, Any]:
        params = {k: v for k, v in kw.items() if v is not None}
        result = await self._search.get_model("/search", _Items, params=params)
        return {"as_of": result.as_of, "items": [i for i in result.items if self._allowed(i)]}

    async def search_research(self, **kw: Any) -> dict[str, Any]:
        params = {k: v for k, v in kw.items() if v is not None}
        result = await self._research.get_model("/research/search", _Items, params=params)
        return result.model_dump()

    async def health(self) -> bool:
        return await self._search.health() and await self._research.health()
