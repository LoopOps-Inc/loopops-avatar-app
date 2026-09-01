"""Suitability engine tests. The replay suite gates at 100 % (ADR-0005)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

from actinver_agent.graph.state import (
    Complexity,
    InvestorProfile,
    KnowledgeLevel,
    ProductProfile,
    RiskCategory,
    RiskLevel,
    SuitabilityOutcome,
)
from actinver_agent.suitability.engine import SuitabilityEngine
from actinver_agent.suitability.inprocess import InProcessSuitability
from actinver_agent.suitability.replay import load_corpus, replay_corpus
from actinver_agent.suitability.rules import RULESETS, EvaluationContext, get_ruleset

KEY = b"test-key-not-for-production"
TODAY = date(2026, 9, 1)


@pytest.fixture
def engine() -> SuitabilityEngine:
    return SuitabilityEngine(14, KEY)


@pytest.fixture
def moderate_profile() -> InvestorProfile:
    return InvestorProfile(
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


def _product(**overrides: object) -> ProductProfile:
    base: dict = {
        "product_id": "ACTIGOB-BF",
        "name": "Actinver Gubernamental",
        "committee_version": 31,
        "risk_level": RiskLevel.BAJO,
        "complexity": Complexity.SIMPLE,
        "liquidity_hours": 24,
        "min_holding_months": 1,
        "minimum_investment": Decimal("10000"),
        "currency": "MXN",
        "annual_cost_pct": 0.85,
        "asset_class": "deuda_gubernamental",
        "approved_at": date(2026, 6, 1),
    }
    return ProductProfile(**(base | overrides))  # type: ignore[arg-type]


def _ctx(amount: str = "100000") -> EvaluationContext:
    return EvaluationContext(
        today=TODAY,
        amount=Decimal(amount),
        portfolio_total=Decimal("4000000"),
        current_weight_by_product={},
        current_weight_by_asset_class={},
        liquid_pct=0.30,
        diversification_limits={"__default__": 0.25},
    )


def test_congruent_product_is_apto(engine, moderate_profile) -> None:
    report = engine.evaluate(moderate_profile, [_product()], _ctx())
    assert report.evaluations[0].outcome is SuitabilityOutcome.APTO
    assert report.verdict_id.startswith("sv_")
    assert engine.verify(report)


def test_risk_above_profile_ceiling_is_no_apto(engine, moderate_profile) -> None:
    report = engine.evaluate(moderate_profile, [_product(risk_level=RiskLevel.ALTO)], _ctx())
    evaluation = report.evaluations[0]
    assert evaluation.outcome is SuitabilityOutcome.NO_APTO
    assert evaluation.rule_id == "R-004"
    assert "riesgo" in evaluation.rationale.lower()


def test_holding_period_beyond_horizon_is_no_apto(engine, moderate_profile) -> None:
    report = engine.evaluate(moderate_profile, [_product(min_holding_months=36)], _ctx())
    assert report.evaluations[0].rule_id == "R-007"


def test_expired_profile_blocks_everything(engine, moderate_profile) -> None:
    expired = moderate_profile.model_copy(update={"expires_at": date(2026, 1, 1)})
    report = engine.evaluate(expired, [_product()], _ctx())
    assert report.evaluations[0].rule_id == "R-001"


def test_complexity_above_knowledge_warns_but_does_not_block(engine, moderate_profile) -> None:
    report = engine.evaluate(moderate_profile, [_product(complexity=Complexity.COMPLEJA)], _ctx())
    evaluation = report.evaluations[0]
    assert evaluation.outcome is SuitabilityOutcome.APTO_CON_ADVERTENCIA
    assert evaluation.warnings


def test_concentration_limit_is_enforced(engine, moderate_profile) -> None:
    report = engine.evaluate(moderate_profile, [_product()], _ctx(amount="3000000"))
    assert report.evaluations[0].rule_id == "R-012"


def test_below_minimum_investment_is_no_apto(engine, moderate_profile) -> None:
    report = engine.evaluate(moderate_profile, [_product()], _ctx(amount="5000"))
    assert report.evaluations[0].rule_id == "R-014"


def test_currency_and_liquidity_warnings(engine, moderate_profile) -> None:
    report = engine.evaluate(moderate_profile, [_product(currency="USD")], _ctx())
    assert report.evaluations[0].outcome is SuitabilityOutcome.APTO_CON_ADVERTENCIA
    illiquid_profile = moderate_profile.model_copy(update={"min_liquidity_pct": 0.95})
    report = engine.evaluate(illiquid_profile, [_product(liquidity_hours=None)], _ctx())
    assert report.evaluations[0].outcome is SuitabilityOutcome.APTO_CON_ADVERTENCIA


def test_verdict_is_deterministic(engine, moderate_profile) -> None:
    products = [_product(), _product(product_id="X", risk_level=RiskLevel.ALTO)]
    first = engine.evaluate(moderate_profile, products, _ctx())
    second = engine.evaluate(moderate_profile, products, _ctx())
    assert first.signature == second.signature
    assert first.verdict_id == second.verdict_id


def test_signature_detects_tampering(engine, moderate_profile) -> None:
    report = engine.evaluate(moderate_profile, [_product(risk_level=RiskLevel.ALTO)], _ctx())
    forged = report.model_copy(
        update={
            "evaluations": [
                report.evaluations[0].model_copy(update={"outcome": SuitabilityOutcome.APTO})
            ]
        }
    )
    assert not engine.verify(forged)
    other_key = SuitabilityEngine(14, b"another-key")
    assert not other_key.verify(report)


def test_rulesets_are_append_only() -> None:
    assert 14 in RULESETS
    assert [r.rule_id for r in get_ruleset(14)] == [
        "R-001",
        "R-004",
        "R-007",
        "R-009",
        "R-012",
        "R-014",
        "R-016",
        "R-018",
    ]
    with pytest.raises(ValueError, match="append-only"):
        get_ruleset(99)


def test_replay_corpus_matches_100_percent() -> None:
    corpus = load_corpus()
    mismatches = replay_corpus(corpus)
    assert corpus["cases"], "corpus must not be empty"
    assert mismatches == [], mismatches[:3]


async def test_inprocess_port() -> None:
    from actinver_agent.ports import EvaluationInput

    port = InProcessSuitability.with_key(KEY)
    profile = InvestorProfile(
        profile_id="pf",
        version=1,
        risk_category=RiskCategory.AGRESIVO,
        horizon_months=60,
        knowledge_level=KnowledgeLevel.AVANZADO,
        capacity_band="C",
        assessed_at=TODAY,
        expires_at=date(2027, 9, 1),
    )
    ctx = EvaluationInput(
        today=datetime.now(UTC),
        amount=Decimal("50000"),
        portfolio_total=Decimal("1000000"),
        current_weight_by_product={},
        current_weight_by_asset_class={},
        liquid_pct=0.5,
        diversification_limits={"__default__": 0.25},
    )
    report = await port.evaluate(
        client_id="cl", profile=profile, products=[_product(risk_level=RiskLevel.ALTO)], ctx=ctx
    )
    assert report.evaluations[0].outcome is SuitabilityOutcome.APTO
    assert await port.verify(report=report)


risk_levels = st.sampled_from(list(RiskLevel))
categories = st.sampled_from(list(RiskCategory))
_SEVERITY = {
    SuitabilityOutcome.APTO: 0,
    SuitabilityOutcome.APTO_CON_ADVERTENCIA: 1,
    SuitabilityOutcome.NO_APTO: 2,
}
_ORDER = [RiskLevel.BAJO, RiskLevel.MEDIO, RiskLevel.ALTO]


@h_settings(max_examples=150, deadline=None)
@given(
    category=categories, risk=risk_levels, amount=st.integers(min_value=10_000, max_value=900_000)
)
def test_raising_product_risk_never_improves_the_verdict(
    category: RiskCategory, risk: RiskLevel, amount: int
) -> None:
    engine = SuitabilityEngine(14, KEY)
    profile = InvestorProfile(
        profile_id="pf",
        version=1,
        risk_category=category,
        horizon_months=36,
        knowledge_level=KnowledgeLevel.AVANZADO,
        capacity_band="B",
        assessed_at=TODAY,
        expires_at=date(2027, 1, 1),
    )
    ctx = _ctx(str(amount))
    outcomes = []
    for level in _ORDER[_ORDER.index(risk) :]:
        report = engine.evaluate(profile, [_product(risk_level=level)], ctx)
        outcomes.append(_SEVERITY[report.evaluations[0].outcome])
    assert outcomes == sorted(outcomes), "monotonicity: more risk can never be more suitable"
