"""The suitability engine (ADR-0005).

Properties this module must preserve, in order of importance:

1. **Deterministic.** Same inputs and version → same verdict, forever.
2. **Explainable.** The failing rule *is* the rationale; nothing is generated.
3. **Signed.** HMAC-SHA256 with a key held by suitability-service only, so a
   compromised agent cannot forge an APTO.
4. **Replayable.** ``replay()`` reproduces a historical verdict from a stored
   input snapshot; CI asserts 100 % match against a labelled corpus.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from typing import Any

import orjson

from actinver_agent.graph.state import (
    InvestorProfile,
    ProductProfile,
    SuitabilityEvaluation,
    SuitabilityOutcome,
    SuitabilityReport,
)
from actinver_agent.suitability.rules import EvaluationContext, get_ruleset

_SEVERITY = {
    SuitabilityOutcome.APTO: 0,
    SuitabilityOutcome.APTO_CON_ADVERTENCIA: 1,
    SuitabilityOutcome.NO_APTO: 2,
}


class SuitabilityEngine:
    def __init__(
        self, ruleset_version: int, signing_key: bytes, *, signing_key_version: int = 1
    ) -> None:
        self._version = ruleset_version
        self._rules = get_ruleset(ruleset_version)
        self._key = signing_key
        self._key_version = signing_key_version

    @property
    def ruleset_version(self) -> int:
        return self._version

    def evaluate(
        self,
        profile: InvestorProfile,
        products: list[ProductProfile],
        ctx: EvaluationContext,
        *,
        evaluated_at: datetime | None = None,
    ) -> SuitabilityReport:
        evaluations = [self._evaluate_one(profile, p, ctx) for p in products]
        body = self._report_body(profile, evaluations, ctx)
        signature = self._sign(body)
        return SuitabilityReport(
            verdict_id=f"sv_{signature[:26]}",
            ruleset_version=self._version,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            amount=str(ctx.amount),
            evaluated_at=evaluated_at or datetime.now(UTC),
            evaluations=evaluations,
            signature=signature,
            signing_key_version=self._key_version,
        )

    def _evaluate_one(
        self, profile: InvestorProfile, product: ProductProfile, ctx: EvaluationContext
    ) -> SuitabilityEvaluation:
        worst = SuitabilityOutcome.APTO
        failing_rule: str | None = None
        rationale_parts: list[str] = []
        warnings: list[str] = []

        for rule in self._rules:
            if rule.predicate(profile, product, ctx):
                continue
            if rule.on_fail is SuitabilityOutcome.APTO_CON_ADVERTENCIA:
                warnings.append(rule.message_es)
            if _SEVERITY[rule.on_fail] > _SEVERITY[worst]:
                worst = rule.on_fail
                failing_rule = rule.rule_id
            rationale_parts.append(f"[{rule.rule_id}] {rule.message_es}")
            # A NO_APTO is terminal: no later rule can rehabilitate it, and
            # stopping keeps the rationale focused on the disqualifying reason.
            if rule.on_fail is SuitabilityOutcome.NO_APTO:
                break

        if worst is SuitabilityOutcome.APTO:
            rationale = (
                f"Congruente: riesgo {product.risk_level} ≤ perfil "
                f"{profile.max_risk}; permanencia {product.min_holding_months}m ≤ "
                f"horizonte {profile.horizon_months}m; dentro de límites de "
                f"diversificación."
            )
        else:
            rationale = " ".join(rationale_parts)

        return SuitabilityEvaluation(
            product_id=product.product_id,
            product_profile_version=product.committee_version,
            outcome=worst,
            rule_id=failing_rule,
            rationale=rationale,
            warnings=warnings,
        )

    def _report_body(
        self,
        profile: InvestorProfile,
        evaluations: list[SuitabilityEvaluation],
        ctx: EvaluationContext,
    ) -> dict[str, Any]:
        return {
            "ruleset_version": self._version,
            "profile_id": profile.profile_id,
            "profile_version": profile.version,
            "amount": str(ctx.amount),
            "evaluations": [e.model_dump(mode="json") for e in evaluations],
        }

    def _sign(self, body: dict[str, Any]) -> str:
        canonical = orjson.dumps(body, option=orjson.OPT_SORT_KEYS)
        return hmac.new(self._key, canonical, hashlib.sha256).hexdigest()

    def verify(self, report: SuitabilityReport) -> bool:
        expected = self._sign(
            {
                "ruleset_version": report.ruleset_version,
                "profile_id": report.profile_id,
                "profile_version": report.profile_version,
                "amount": report.amount,
                "evaluations": [e.model_dump(mode="json") for e in report.evaluations],
            }
        )
        return hmac.compare_digest(expected, report.signature)

    def replay(self, snapshot: dict[str, Any]) -> SuitabilityReport:
        """Reproduce a verdict from a stored input snapshot
        (profile, products, evaluation context)."""
        profile = InvestorProfile.model_validate(snapshot["profile"])
        products = [ProductProfile.model_validate(p) for p in snapshot["products"]]
        ctx = EvaluationContext.from_snapshot(snapshot["context"])
        return self.evaluate(profile, products, ctx, evaluated_at=datetime.min.replace(tzinfo=UTC))


def snapshot_inputs(
    profile: InvestorProfile, products: list[ProductProfile], ctx: EvaluationContext
) -> dict[str, Any]:
    return {
        "profile": profile.model_dump(mode="json"),
        "products": [p.model_dump(mode="json") for p in products],
        "context": ctx.snapshot(),
    }
