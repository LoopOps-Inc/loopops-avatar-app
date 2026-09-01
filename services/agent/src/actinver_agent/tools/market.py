"""Market data, news retrieval and economic calendar tools.

The news and research tools are the one place where untrusted third-party text
enters the prompt. They are treated as an injection vector by default
(``untrusted_content=True``): the agent wraps retrieved text in a
``<contenido_externo>`` block, the guardrail scans every item before the model
sees it, and the system prompt states the block is data, never instruction.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from actinver_agent.ports import MarketDataPort, NewsPort
from actinver_agent.tools import results
from actinver_agent.tools.registry import ToolArgs, ToolRegistry, ToolSpec

if TYPE_CHECKING:
    from actinver_agent.retrieval.retriever import Retriever


class QuoteArgs(ToolArgs):
    symbols: list[str] = Field(
        min_length=1,
        max_length=10,
        description="Claves de pizarra (BMV/BIVA/SIC), índices, divisas o tasas",
    )


class NewsArgs(ToolArgs):
    query: str = Field(max_length=200, description="Tema a buscar, en español")
    since: date | None = Field(default=None, description="Sólo noticias posteriores")
    limit: int = Field(default=5, le=10, ge=1)
    language: Literal["es", "en"] = "es"


class ResearchArgs(ToolArgs):
    query: str = Field(max_length=200)
    limit: int = Field(default=4, le=8, ge=1)


class CalendarArgs(ToolArgs):
    since: date | None = None
    until: date | None = None
    regions: list[Literal["MX", "US", "GLOBAL"]] = Field(default=["MX"])


def register(
    registry: ToolRegistry,
    market: MarketDataPort,
    news: NewsPort,
    retriever: Retriever | None = None,
) -> None:
    registry.register(
        ToolSpec(
            name="get_market_quote",
            description_es=(
                "Cotización de instrumentos, índices, tipos de cambio y tasas de "
                "referencia (CETES, TIIE). Incluye la marca de tiempo y si el precio "
                "tiene retraso. Nunca cites un precio sin mencionar su fecha."
            ),
            args_schema=QuoteArgs,
            fn=market.get_quotes,
            requires_client=False,
            classification="PUBLIC",
            cache_ttl_s=15,
            fail_open=True,
            tags=("market",),
            result_model=results.QuotesResult,
        )
    )

    registry.register(
        ToolSpec(
            name="search_market_news",
            description_es=(
                "Busca noticias financieras recientes en fuentes autorizadas. "
                "Devuelve titular, resumen, fuente, fecha y enlace. Toda afirmación "
                "que tomes de aquí debe ir acompañada de su fuente y fecha."
            ),
            args_schema=NewsArgs,
            fn=news.search,
            requires_client=False,
            classification="PUBLIC",
            cache_ttl_s=900,
            timeout_s=4.0,
            fail_open=True,
            untrusted_content=True,
            tags=("news", "untrusted_content"),
            result_model=results.NewsResult,
        )
    )

    async def research(**kw: Any) -> dict[str, Any]:
        if retriever is not None:
            return await retriever.search_as_tool(
                "research_notes", query=kw["query"], k=int(kw.get("limit") or 4)
            )
        return await news.search_research(**kw)

    registry.register(
        ToolSpec(
            name="get_actinver_research",
            description_es=(
                "Consulta las notas de análisis y research propio de Actinver. "
                "Prefiere esta fuente sobre la prensa cuando ambas apliquen."
            ),
            args_schema=ResearchArgs,
            fn=research,
            requires_client=False,
            classification="INTERNAL",
            cache_ttl_s=1800,
            fail_open=True,
            untrusted_content=True,
            tags=("research",),
            result_model=results.NewsResult,
        )
    )

    registry.register(
        ToolSpec(
            name="get_economic_calendar",
            description_es=(
                "Calendario económico: decisiones de Banxico y de la Fed, INPC, "
                "empleo, reportes trimestrales relevantes."
            ),
            args_schema=CalendarArgs,
            fn=market.get_calendar,
            requires_client=False,
            classification="PUBLIC",
            cache_ttl_s=3600,
            fail_open=True,
            tags=("market",),
            result_model=results.CalendarResult,
        )
    )
