"""The tool catalogue (docs/04-backend/03) assembled against the ports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from actinver_agent.ports import CoreBankingPort, CrmPort, MarketDataPort, NewsPort, SuitabilityPort
from actinver_agent.tools import market, portfolio, products, support, transactions
from actinver_agent.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from actinver_agent.retrieval.retriever import Retriever


def build_registry(
    core: CoreBankingPort,
    market_data: MarketDataPort,
    news: NewsPort,
    crm: CrmPort,
    suitability: SuitabilityPort,
    retriever: Retriever | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    portfolio.register(registry, core)
    products.register(registry, core, suitability)
    market.register(registry, market_data, news, retriever)
    transactions.register(registry, core)
    support.register(registry, crm)
    return registry
