"""The suitability gate - the hard, deterministic node in the graph (ADR-0005).

Products marked NO_APTO are stripped from state *before* the composer runs, so
the model cannot mention them even if the prompt failed to dissuade it; the
stripped names are also handed to ``compliance_guard`` as forbidden terms.
The verdict comes from ``suitability-service``; if it is unreachable the
advisory turn fails closed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

from actinver_agent.deps import Dependencies
from actinver_agent.graph.state import AdvisorState, AgentError, SuitabilityOutcome
from actinver_agent.observability.setup import get_metrics, node_span
from actinver_agent.tools.products import build_evaluation_input

log = structlog.get_logger(__name__)

NO_PROFILE_ES = (
    "No pude consultar tu perfil de inversionista en este momento. "
    "Intentemos de nuevo en un momento."
)
NO_SUITABLE_ES = (
    "Ninguno de los productos que revisé es congruente con tu perfil de "
    "inversionista. Prefiero que lo veas con tu asesor para encontrar una "
    "alternativa adecuada. ¿Te comunico?"
)
SUITABILITY_DOWN_ES = (
    "No puedo validar una recomendación en este momento. Te comunico con tu "
    "asesor para revisarlo juntos."
)


async def suitability_gate(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    if state.get("error") is not None:
        return {}
    profile = state.get("investor_profile")
    candidates = state.get("candidate_products", [])
    if profile is None:
        return {"error": AgentError(code="NO_PROFILE", message_es=NO_PROFILE_ES, escalate=True)}
    if not candidates:
        return {}

    client_id = state["client_id"]
    positions_result = await deps.gateway.call(
        "get_portfolio_positions", client_id=client_id, args={}
    )
    if not positions_result.ok or not isinstance(positions_result.data, dict):
        # Concentration and liquidity rules need the live portfolio: fail closed.
        return {
            "error": AgentError(
                code="SUITABILITY_UNAVAILABLE", message_es=SUITABILITY_DOWN_ES, escalate=True
            )
        }
    try:
        limits = await deps.core.get_diversification_limits()
    except Exception as exc:
        log.error("suitability.limits_unavailable", reason=type(exc).__name__)
        return {
            "error": AgentError(
                code="SUITABILITY_UNAVAILABLE", message_es=SUITABILITY_DOWN_ES, escalate=True
            )
        }

    proposed = state.get("proposed_amount")
    amount = proposed.decimal if proposed is not None else Decimal("0")
    ctx = build_evaluation_input(amount=amount, positions=positions_result.data, limits=limits)

    with node_span("suitability_gate", turn_id=state.get("turn_id"), candidates=len(candidates)):
        try:
            report = await deps.suitability.evaluate(
                client_id=client_id, profile=profile, products=candidates, ctx=ctx
            )
        except Exception as exc:
            log.error("suitability.unavailable", reason=type(exc).__name__)
            return {
                "error": AgentError(
                    code="SUITABILITY_UNAVAILABLE", message_es=SUITABILITY_DOWN_ES, escalate=True
                )
            }

    metrics = get_metrics()
    for evaluation in report.evaluations:
        metrics.suitability_outcomes.add(
            1,
            {
                "outcome": str(evaluation.outcome),
                "rule": evaluation.rule_id or "none",
                "ruleset": str(report.ruleset_version),
            },
        )
    approved = set(report.approved_product_ids)
    surviving = [p for p in candidates if p.product_id in approved]
    stripped = [p for p in candidates if p.product_id not in approved]
    rejected = [e for e in report.evaluations if e.outcome is SuitabilityOutcome.NO_APTO]
    if rejected:
        log.info(
            "suitability.rejected",
            count=len(rejected),
            rules=[e.rule_id for e in rejected],
            ruleset=report.ruleset_version,
            turn_id=state.get("turn_id"),
        )

    update: dict[str, Any] = {
        "suitability": report,
        "candidate_products": surviving,
        "stripped_products": stripped,
    }
    if not surviving:
        update["error"] = AgentError(
            code="NO_SUITABLE_PRODUCT", message_es=NO_SUITABLE_ES, escalate=True
        )
    return update
