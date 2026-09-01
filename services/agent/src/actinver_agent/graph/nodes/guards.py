"""Ingress and egress guardrail nodes. Both fail closed.

The checks themselves live in ``guardrail-service`` (reached through the
``GuardrailPort``); these nodes translate verdicts into graph state. If the
service is unreachable, no response is emitted (docs/01-architecture/01 §7).
"""

from __future__ import annotations

from typing import Any

import structlog

from actinver_agent.deps import Dependencies
from actinver_agent.graph.state import (
    AdvisorState,
    AgentError,
    GuardrailAction,
    GuardrailVerdict,
)
from actinver_agent.observability.setup import get_metrics, node_span
from actinver_agent.ports import OutputCheckRequest

log = structlog.get_logger(__name__)

GUARDRAIL_DOWN_ES = (
    "No puedo responder en este momento por un problema técnico. Te comunico con tu asesor."
)
BLOCKED_INPUT_ES = (
    "Sólo puedo ayudarte con temas de tus inversiones en Actinver. "
    "¿Qué te gustaría saber de tu portafolio?"
)
LOW_CONFIDENCE_ES = "No te escuché bien. ¿Me lo repites, por favor?"
DISTRESS_ES = (
    "Entiendo que es una situación delicada. Te comunico de inmediato con tu "
    "asesor para que te acompañe."
)
ABUSE_ES = "Estoy aquí para ayudarte con tus inversiones. Si prefieres, te comunico con tu asesor."
BLOCKED_OUTPUT_ES = (
    "Prefiero no responder eso sin que lo revise un asesor. ¿Te comunico con el tuyo?"
)


async def ingress_guard(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    """Runs before any model call. Rate limiting happened in the API layer."""
    text = state.get("client_input_text", "")
    with node_span("ingress_guard", turn_id=state.get("turn_id")):
        try:
            verdict, redacted = await deps.guardrail.check_input(
                text=text, transcript_confidence=state.get("transcript_confidence")
            )
        except Exception as exc:
            log.error("ingress.guardrail_unavailable", reason=type(exc).__name__)
            return {
                "guardrail_input": GuardrailVerdict(
                    action=GuardrailAction.BLOCK, violations=["GUARDRAIL_UNAVAILABLE"]
                ),
                "error": AgentError(
                    code="GUARDRAIL_UNAVAILABLE", message_es=GUARDRAIL_DOWN_ES, escalate=True
                ),
            }

    if verdict.redactions:
        log.info("ingress.redacted", count=verdict.redactions, turn_id=state.get("turn_id"))

    if verdict.action is GuardrailAction.BLOCK or verdict.detail in ("DISTRESS", "ABUSE"):
        get_metrics().guardrail_blocks.add(
            1, {"stage": "input", "reason": verdict.violations[0] if verdict.violations else "n/a"}
        )
        code, message, escalate, distress = _refusal_for(verdict)
        log.warning(
            "ingress.blocked",
            code=code,
            score=round(verdict.injection_score, 2),
            hits=verdict.violations,
            turn_id=state.get("turn_id"),
        )
        return {
            "guardrail_input": verdict,
            "client_input_text": redacted,
            "distress": distress,
            "error": AgentError(code=code, message_es=message, escalate=escalate),
        }

    return {"guardrail_input": verdict, "client_input_text": redacted, "distress": False}


def _refusal_for(verdict: GuardrailVerdict) -> tuple[str, str, bool, bool]:
    violations = set(verdict.violations)
    if "LOW_ASR_CONFIDENCE" in violations:
        return "LOW_CONFIDENCE", LOW_CONFIDENCE_ES, False, False
    if verdict.detail == "DISTRESS" or "DISTRESS" in violations:
        # Distress and fraud mentions escalate to a human immediately.
        return "DISTRESS_ESCALATION", DISTRESS_ES, True, True
    if verdict.detail == "ABUSE" or "ABUSE" in violations:
        return "ABUSE_WARNING", ABUSE_ES, True, False
    if verdict.detail == "OUT_OF_SCOPE" or any(v.startswith("OUT_OF_SCOPE") for v in violations):
        return "OUT_OF_SCOPE", BLOCKED_INPUT_ES, True, False
    return "BLOCKED_INPUT", BLOCKED_INPUT_ES, True, False


async def compliance_guard(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    """Output filter (docs/01-architecture/06 §3.7). REWRITE at most twice."""
    speech = state.get("speech") or ""
    stripped = state.get("stripped_products", [])
    terms = tuple(t for p in stripped for t in (p.product_id, p.name) if t)
    request = OutputCheckRequest(
        speech=speech,
        intent=state.get("intent"),
        locale=state.get("locale", "es-MX"),
        register=state.get("register", "tu"),
        provenance_keys=frozenset(state.get("provenance", {}).keys()),
        stripped_product_terms=terms,
        rewrite_attempts=state.get("rewrite_attempts", 0),
        max_rewrite_attempts=deps.settings.limits.max_rewrite_attempts,
    )
    with node_span(
        "compliance_guard", turn_id=state.get("turn_id"), rewrites=request.rewrite_attempts
    ):
        try:
            verdict = await deps.guardrail.check_output(request)
        except Exception as exc:
            log.error("egress.guardrail_unavailable", reason=type(exc).__name__)
            return {
                "speech": None,
                "guardrail_output": GuardrailVerdict(
                    action=GuardrailAction.BLOCK, violations=["GUARDRAIL_UNAVAILABLE"]
                ),
                "error": AgentError(
                    code="GUARDRAIL_UNAVAILABLE", message_es=GUARDRAIL_DOWN_ES, escalate=True
                ),
            }

    if verdict.action is GuardrailAction.PASS:
        shown: dict[str, str] = {}
        texts: dict[str, str] = {}
        if verdict.disclosures_injected:
            try:
                resolved = await deps.guardrail.disclosure_texts(list(verdict.disclosures_injected))
            except Exception as exc:
                log.error("egress.disclosures_unavailable", reason=type(exc).__name__)
                return {
                    "speech": None,
                    "guardrail_output": GuardrailVerdict(
                        action=GuardrailAction.BLOCK, violations=["DISCLOSURES_UNAVAILABLE"]
                    ),
                    "error": AgentError(
                        code="GUARDRAIL_UNAVAILABLE", message_es=GUARDRAIL_DOWN_ES, escalate=True
                    ),
                }
            for disclosure_id, (text, version) in resolved.items():
                shown[disclosure_id] = version
                texts[disclosure_id] = text
        return {"guardrail_output": verdict, "disclosures_shown": shown, "disclosure_texts": texts}

    if verdict.action is GuardrailAction.REWRITE:
        get_metrics().guardrail_rewrites.add(1)
        log.info(
            "egress.rewrite",
            violations=verdict.violations,
            attempt=state.get("rewrite_attempts", 0) + 1,
            turn_id=state.get("turn_id"),
        )
        return {
            "guardrail_output": verdict,
            "rewrite_attempts": state.get("rewrite_attempts", 0) + 1,
        }

    get_metrics().guardrail_blocks.add(
        1, {"stage": "output", "reason": verdict.violations[0] if verdict.violations else "n/a"}
    )
    log.warning("egress.blocked", violations=verdict.violations, turn_id=state.get("turn_id"))
    return {
        "speech": None,
        "guardrail_output": verdict,
        "error": AgentError(code="BLOCKED_OUTPUT", message_es=BLOCKED_OUTPUT_ES, escalate=True),
    }
