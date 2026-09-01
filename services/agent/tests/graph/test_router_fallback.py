"""The router degrades to the deterministic rules classifier when the model
provider fails (ADR-0003 fallback), instead of failing the turn."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from actinver_agent.deps import Dependencies
from actinver_agent.graph.nodes.agent_core import (
    _candidate_ids_from_tools,
    _ensure_transactional_tools,
    _search_filters,
)
from actinver_agent.graph.nodes.routing import intent_router
from actinver_agent.graph.state import (
    Intent,
    InvestorProfile,
    KnowledgeLevel,
    RiskCategory,
    ToolResult,
)


class _BrokenClassifier:
    async def classify(self, **_: Any) -> Any:
        raise ValueError("Invalid JSON: EOF while parsing")


async def test_router_falls_back_to_rules_when_the_model_fails(
    deps: Dependencies, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deps, "classifier", _BrokenClassifier())
    state: dict[str, Any] = {
        "client_input_text": "¿Cómo va mi portafolio?",
        "messages": [],
        "locale": "es-MX",
        "turn_id": "tn_test",
    }
    update = await intent_router(state, deps)  # type: ignore[arg-type]
    assert update["intent"] is Intent.PORTFOLIO_INSPECT


def test_transaction_requirements_is_forced_when_the_model_only_checks_suitability() -> None:
    """mode=ANY returns a single call: a real model emits check_suitability and
    drops get_transaction_requirements. The graph must add it so the FormSpec can
    be built (regression: real Gemini produced REQUIREMENTS_UNAVAILABLE)."""
    state = {
        "intent": Intent.TRANSACT_BUY,
        "client_input_text": "Quiero invertir 100 mil en ACTIGOB-BF",
    }
    planned = [
        {"name": "check_suitability", "args": {"product_id": "ACTIGOB-BF", "amount": 100000}}
    ]
    out = _ensure_transactional_tools(state, planned)  # type: ignore[arg-type]
    names = [c["name"] for c in out]
    assert "get_transaction_requirements" in names
    req = next(c for c in out if c["name"] == "get_transaction_requirements")
    assert req["args"] == {"product_id": "ACTIGOB-BF", "operation": "BUY", "amount": "100000"}


def test_suitability_is_forced_when_the_model_only_gets_requirements() -> None:
    state = {"intent": Intent.TRANSACT_BUY, "client_input_text": "Compra ACTIGOB-BF"}
    planned = [
        {
            "name": "get_transaction_requirements",
            "args": {"product_id": "ACTIGOB-BF", "operation": "BUY", "amount": "100000"},
        }
    ]
    out = _ensure_transactional_tools(state, planned)  # type: ignore[arg-type]
    assert "check_suitability" in [c["name"] for c in out]


def test_non_transactional_intent_is_left_untouched() -> None:
    state = {"intent": Intent.PORTFOLIO_INSPECT, "client_input_text": "¿Cómo va mi portafolio?"}
    planned = [{"name": "get_portfolio_positions", "args": {}}]
    assert _ensure_transactional_tools(state, planned) == planned  # type: ignore[arg-type]


def test_advisory_forces_product_search_when_the_model_skips_it() -> None:
    state = {"intent": Intent.ADVISORY_RECOMMEND, "client_input_text": "¿Dónde invierto 200 mil?"}
    out = _ensure_transactional_tools(state, [{"name": "get_portfolio_positions", "args": {}}])  # type: ignore[arg-type]
    assert "search_investment_products" in [c["name"] for c in out]


def test_candidate_ids_fall_back_to_search_results() -> None:
    """When the model omits the <candidatos> block, candidates come from the
    search tool results so the suitability verdict is still produced."""
    state = {
        "tool_results": {
            "search_investment_products": ToolResult(
                name="search_investment_products",
                ok=True,
                data={
                    "items": [
                        {"product_id": "ACTIGOB-BF"},
                        {"product_id": "ACTICOB-BF"},
                        {"product_id": "ACTIGOB-BF"},
                    ]
                },
            )
        }
    }
    assert _candidate_ids_from_tools(state) == ["ACTIGOB-BF", "ACTICOB-BF"]  # type: ignore[arg-type]


def test_forced_advisory_search_is_scoped_to_the_profile_risk_and_horizon() -> None:
    """A forced search must be profile-scoped: an unfiltered search returns
    products the profile rejects, so every candidate fails suitability (R-014/risk)."""
    profile = InvestorProfile(
        profile_id="pf_1",
        version=7,
        risk_category=RiskCategory.MODERADO,
        horizon_months=24,
        knowledge_level=KnowledgeLevel.INTERMEDIO,
        capacity_band="B",
        permitted_currencies=["MXN"],
        min_liquidity_pct=0.10,
        assessed_at=date(2026, 2, 11),
        expires_at=date(2027, 2, 11),
    )
    filters = _search_filters({"investor_profile": profile})  # type: ignore[arg-type]
    assert filters["risk_level"] == ["bajo", "medio"]
    assert filters["horizon_months_max"] == 24
