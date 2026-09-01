"""Deterministic razonabilidad rules - DCGSI Art. 5 (ADR-0005).

Owned by Compliance, not Engineering. Rule sets are append-only: version 14 is
never edited; version 15 supersedes it. Every verdict records the version that
produced it so a 2031 audit can replay a 2026 decision exactly.

Diversification limits are supplied by the committee at evaluation time, never
hardcoded here (docs/07-data-governance/01 §4).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from actinver_agent.graph.state import (
    COMPLEXITY_ORDER,
    KNOWLEDGE_ORDER,
    RISK_ORDER,
    InvestorProfile,
    ProductProfile,
    SuitabilityOutcome,
)
from actinver_agent.ports import EvaluationInput


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    """Everything a rule may look at, and nothing more."""

    today: date
    amount: Decimal
    portfolio_total: Decimal
    current_weight_by_product: dict[str, float]
    current_weight_by_asset_class: dict[str, float]
    liquid_pct: float
    diversification_limits: dict[str, float]

    @classmethod
    def from_input(cls, data: EvaluationInput) -> EvaluationContext:
        return cls(
            today=data.today.date() if hasattr(data.today, "date") else data.today,
            amount=Decimal(str(data.amount)),
            portfolio_total=Decimal(str(data.portfolio_total)),
            current_weight_by_product=dict(data.current_weight_by_product),
            current_weight_by_asset_class=dict(data.current_weight_by_asset_class),
            liquid_pct=float(data.liquid_pct),
            diversification_limits=dict(data.diversification_limits),
        )

    def post_trade_weight(self, product: ProductProfile) -> float:
        total = self.portfolio_total + self.amount
        if total == 0:
            return 0.0
        current = (
            Decimal(str(self.current_weight_by_product.get(product.product_id, 0.0)))
            * self.portfolio_total
        )
        return float((current + self.amount) / total)

    def diversification_limit(self, product: ProductProfile) -> float:
        """Limits set by the comité responsable del análisis de productos
        financieros (DCGSI Art. 6, Art. 20)."""
        return self.diversification_limits.get(
            product.asset_class,
            self.diversification_limits.get("__default__", 0.25),
        )

    def post_trade_liquid_pct(self, product: ProductProfile) -> float:
        total = self.portfolio_total + self.amount
        if total == 0:
            return 0.0
        liquid = Decimal(str(self.liquid_pct)) * self.portfolio_total
        if product.liquidity_hours is not None and product.liquidity_hours <= 72:
            liquid += self.amount
        return float(liquid / total)

    def snapshot(self) -> dict[str, Any]:
        return {
            "today": self.today.isoformat(),
            "amount": str(self.amount),
            "portfolio_total": str(self.portfolio_total),
            "current_weight_by_product": self.current_weight_by_product,
            "current_weight_by_asset_class": self.current_weight_by_asset_class,
            "liquid_pct": self.liquid_pct,
            "diversification_limits": self.diversification_limits,
        }

    @classmethod
    def from_snapshot(cls, snap: dict[str, Any]) -> EvaluationContext:
        return cls(
            today=date.fromisoformat(snap["today"]),
            amount=Decimal(snap["amount"]),
            portfolio_total=Decimal(snap["portfolio_total"]),
            current_weight_by_product=dict(snap.get("current_weight_by_product", {})),
            current_weight_by_asset_class=dict(snap.get("current_weight_by_asset_class", {})),
            liquid_pct=float(snap.get("liquid_pct", 0.0)),
            diversification_limits=dict(snap.get("diversification_limits", {})),
        )


Predicate = Callable[[InvestorProfile, ProductProfile, EvaluationContext], bool]


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: str
    name: str
    predicate: Predicate
    on_fail: SuitabilityOutcome
    message_es: str
    regulatory_ref: str


# ── Ruleset v14 ───────────────────────────────────────────────────────────────

RULESET_V14: tuple[Rule, ...] = (
    Rule(
        "R-001",
        "profile_current",
        lambda c, p, ctx: c.is_current(ctx.today),
        SuitabilityOutcome.NO_APTO,
        "El perfil del inversionista está vencido y debe actualizarse antes de "
        "recibir una recomendación.",
        "DCGSI Art. 4",
    ),
    Rule(
        "R-004",
        "risk_ceiling",
        lambda c, p, ctx: RISK_ORDER[p.risk_level] <= RISK_ORDER[c.max_risk],
        SuitabilityOutcome.NO_APTO,
        "El nivel de riesgo del producto es superior al que corresponde al perfil del cliente.",
        "DCGSI Art. 5",
    ),
    Rule(
        "R-007",
        "horizon_vs_holding",
        lambda c, p, ctx: p.min_holding_months <= c.horizon_months,
        SuitabilityOutcome.NO_APTO,
        "El plazo mínimo de permanencia del producto excede el horizonte de "
        "inversión declarado por el cliente.",
        "DCGSI Art. 5",
    ),
    Rule(
        "R-009",
        "knowledge_vs_complexity",
        lambda c, p, ctx: COMPLEXITY_ORDER[p.complexity] <= KNOWLEDGE_ORDER[c.knowledge_level],
        SuitabilityOutcome.APTO_CON_ADVERTENCIA,
        "La complejidad del producto es superior al nivel de conocimiento y "
        "experiencia declarado por el cliente.",
        "DCGSI Art. 4, Anexo 3",
    ),
    Rule(
        "R-012",
        "concentration",
        lambda c, p, ctx: ctx.post_trade_weight(p) <= ctx.diversification_limit(p),
        SuitabilityOutcome.NO_APTO,
        "La operación excede el límite de diversificación establecido por el "
        "comité responsable del análisis de productos financieros.",
        "DCGSI Art. 6",
    ),
    Rule(
        "R-014",
        "minimum_investment",
        lambda c, p, ctx: ctx.amount >= p.minimum_investment,
        SuitabilityOutcome.NO_APTO,
        "El monto es inferior al mínimo de inversión del producto.",
        "Prospecto del producto",
    ),
    Rule(
        "R-016",
        "currency_match",
        lambda c, p, ctx: p.currency in c.permitted_currencies,
        SuitabilityOutcome.APTO_CON_ADVERTENCIA,
        "El producto implica exposición cambiaria no contemplada en el perfil del cliente.",
        "DCGSI Art. 5",
    ),
    Rule(
        "R-018",
        "liquidity_reserve",
        lambda c, p, ctx: ctx.post_trade_liquid_pct(p) >= c.min_liquidity_pct,
        SuitabilityOutcome.APTO_CON_ADVERTENCIA,
        "La operación reduce la reserva de liquidez por debajo del mínimo "
        "declarado por el cliente.",
        "DCGSI Art. 5",
    ),
)

#: Append-only. Never edit an existing entry; add the next version.
RULESETS: dict[int, tuple[Rule, ...]] = {14: RULESET_V14}
RULESET_PUBLISHED: dict[int, date] = {14: date(2026, 8, 20)}


def get_ruleset(version: int) -> tuple[Rule, ...]:
    try:
        return RULESETS[version]
    except KeyError as exc:
        raise ValueError(
            f"Unknown suitability ruleset version {version}. Rulesets are "
            f"append-only; known versions: {sorted(RULESETS)}"
        ) from exc


def ruleset_as_json(version: int) -> dict[str, Any]:
    """Serialisable description for the ``rules`` schema and the console."""
    rules = get_ruleset(version)
    return {
        "version": version,
        "published_at": RULESET_PUBLISHED.get(version, date.min).isoformat(),
        "rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "on_fail": str(r.on_fail),
                "message_es": r.message_es,
                "regulatory_ref": r.regulatory_ref,
            }
            for r in rules
        ],
    }
