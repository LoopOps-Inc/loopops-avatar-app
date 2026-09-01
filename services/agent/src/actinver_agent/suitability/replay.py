"""Replay harness: 100 % match against a labelled corpus is a build gate
(ADR-0005, docs/01-architecture/06 §6).

``generate_corpus`` produces synthetic profile × product pairs with realistic
distributions. Labels are computed by the frozen v14 engine at generation time,
so the corpus is a regression fixture: any drift in the engine fails the build.
Expert-labelled cases from Compliance are appended to the same file with
``"source": "expert"``.
"""

from __future__ import annotations

import random
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import orjson

from actinver_agent.graph.state import (
    Complexity,
    InvestorProfile,
    KnowledgeLevel,
    ProductProfile,
    RiskCategory,
    RiskLevel,
)
from actinver_agent.suitability.engine import SuitabilityEngine, snapshot_inputs
from actinver_agent.suitability.rules import EvaluationContext

CORPUS_KEY = b"replay-corpus-key-not-for-production"
CORPUS_PATH = Path("tests/corpus/suitability_replay.json")

_ASSET_CLASSES = (
    "deuda_gubernamental",
    "deuda_corporativa",
    "renta_variable_local",
    "renta_variable_global",
    "mixto",
    "cobertura_cambiaria",
    "alternativos",
)


def _random_profile(rng: random.Random, index: int) -> InvestorProfile:
    assessed = date(2025, 1 + rng.randrange(12), 1 + rng.randrange(28))
    expired = rng.random() < 0.08
    if expired:
        expires = date(2026, 1 + rng.randrange(8), 1 + rng.randrange(28))
    else:
        expires = date(2027 + rng.randrange(2), assessed.month, assessed.day)
    return InvestorProfile(
        profile_id=f"pf_{index:05d}",
        version=rng.randrange(1, 12),
        risk_category=rng.choice(list(RiskCategory)),
        horizon_months=rng.choice([3, 6, 12, 18, 24, 36, 48, 60, 120]),
        knowledge_level=rng.choice(list(KnowledgeLevel)),
        capacity_band=rng.choice(["A", "B", "C", "D"]),
        permitted_currencies=rng.choice([["MXN"], ["MXN", "USD"], ["MXN", "USD", "EUR"]]),
        min_liquidity_pct=rng.choice([0.0, 0.05, 0.1, 0.2, 0.3]),
        assessed_at=assessed,
        expires_at=expires,
    )


def _random_product(rng: random.Random, index: int) -> ProductProfile:
    return ProductProfile(
        product_id=f"PRD-{index:04d}",
        name=f"Producto {index}",
        committee_version=rng.randrange(1, 40),
        risk_level=rng.choice(list(RiskLevel)),
        complexity=rng.choice(list(Complexity)),
        liquidity_hours=rng.choice([24, 48, 72, None]),
        min_holding_months=rng.choice([0, 1, 3, 6, 12, 24, 36]),
        minimum_investment=Decimal(str(rng.choice([1000, 5000, 10000, 50000, 100000]))),
        currency=rng.choice(["MXN", "MXN", "MXN", "USD", "EUR"]),
        annual_cost_pct=round(rng.uniform(0.2, 2.5), 2),
        asset_class=rng.choice(_ASSET_CLASSES),
        approved_at=date(2026, 1 + rng.randrange(8), 1 + rng.randrange(28)),
    )


def _random_context(rng: random.Random) -> EvaluationContext:
    total = Decimal(str(rng.choice([50_000, 250_000, 1_000_000, 4_000_000, 12_000_000])))
    return EvaluationContext(
        today=date(2026, 9, 1),
        amount=Decimal(str(rng.choice([2_000, 10_000, 50_000, 100_000, 500_000, 2_000_000]))),
        portfolio_total=total,
        current_weight_by_product={},
        current_weight_by_asset_class={},
        liquid_pct=rng.choice([0.0, 0.1, 0.3, 0.6]),
        diversification_limits={"__default__": rng.choice([0.2, 0.25, 0.35]), "alternativos": 0.1},
    )


def generate_corpus(n: int, seed: int = 20260901, *, ruleset_version: int = 14) -> dict[str, Any]:
    rng = random.Random(seed)  # noqa: S311 - synthetic test data, not security
    engine = SuitabilityEngine(ruleset_version, CORPUS_KEY)
    cases: list[dict[str, Any]] = []
    for i in range(n):
        profile = _random_profile(rng, i)
        products = [_random_product(rng, i * 3 + k) for k in range(rng.randrange(1, 4))]
        ctx = _random_context(rng)
        report = engine.evaluate(profile, products, ctx)
        cases.append(
            {
                "case_id": f"case_{i:05d}",
                "source": "synthetic",
                "inputs": snapshot_inputs(profile, products, ctx),
                "expected": [
                    {"product_id": e.product_id, "outcome": str(e.outcome), "rule_id": e.rule_id}
                    for e in report.evaluations
                ],
            }
        )
    return {"ruleset_version": ruleset_version, "seed": seed, "cases": cases}


def write_corpus(path: Path = CORPUS_PATH, n: int = 2000, seed: int = 20260901) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(generate_corpus(n, seed)))
    return path


def load_corpus(path: Path = CORPUS_PATH) -> dict[str, Any]:
    return orjson.loads(path.read_bytes())  # type: ignore[no-any-return]


def replay_corpus(corpus: dict[str, Any], *, key: bytes = CORPUS_KEY) -> list[dict[str, Any]]:
    """Returns the list of mismatches. Empty means 100 % match."""
    engine = SuitabilityEngine(int(corpus["ruleset_version"]), key)
    mismatches: list[dict[str, Any]] = []
    for case in corpus["cases"]:
        report = engine.replay(case["inputs"])
        actual = [
            {"product_id": e.product_id, "outcome": str(e.outcome), "rule_id": e.rule_id}
            for e in report.evaluations
        ]
        if actual != case["expected"]:
            mismatches.append(
                {"case_id": case["case_id"], "expected": case["expected"], "actual": actual}
            )
    return mismatches
