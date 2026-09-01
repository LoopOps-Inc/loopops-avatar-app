"""Intent routing and entitlement gating (docs/01-architecture/06 §3.2-3.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from actinver_agent.deps import Dependencies
from actinver_agent.graph.state import (
    ADVISORY_INTENTS,
    SERVICE_SUBTYPE,
    TRANSACTIONAL_INTENTS,
    AdvisorState,
    AgentError,
    Intent,
    InvestorProfile,
)
from actinver_agent.observability.setup import get_metrics, node_span

log = structlog.get_logger(__name__)

#: Advisory intents that degrade to an informational equivalent when the client
#: has not contracted advised services (or the advisory flag is off).
_DEGRADATION: dict[Intent, Intent] = {
    Intent.ADVISORY_RECOMMEND: Intent.PRODUCT_DISCOVER,
    Intent.SIMULATE: Intent.PRODUCT_DISCOVER,
}

#: Below this confidence a ``product_discover`` with an advisory runner-up is
#: treated as advisory: over-classifying costs a suitability check,
#: under-classifying is a regulatory breach.
_ADVISORY_BIAS_THRESHOLD = 0.75

NOT_ENTITLED_ADVISORY_ES = (
    "Para darte una recomendación personalizada necesitas tener contratado el "
    "servicio de asesoría. Te puedo describir los productos de forma general, o "
    "comunicarte con tu asesor."
)
NOT_ENTITLED_EXECUTION_ES = (
    "Tu contrato actual no permite operar desde aquí. Te comunico con tu asesor "
    "para que lo revisen juntos."
)
TRANSACTIONAL_DISABLED_ES = (
    "Por el momento no es posible preparar operaciones desde el asistente. "
    "Tu asesor puede ayudarte a realizarla."
)
PROFILE_EXPIRED_ES = (
    "Tu perfil de inversionista necesita actualizarse antes de que pueda "
    "recomendarte algo. ¿Lo actualizamos ahora? Toma unos minutos."
)
PROFILE_UNAVAILABLE_ES = (
    "No pude consultar tu perfil de inversionista en este momento, así que no "
    "puedo darte una recomendación. Intentemos de nuevo en un momento o te "
    "comunico con tu asesor."
)


def _history(state: AdvisorState) -> list[str]:
    out: list[str] = []
    for message in state.get("messages", [])[:-1]:
        if isinstance(message, HumanMessage):
            out.append(str(message.content))
    return out[-6:]


async def intent_router(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    text = state.get("client_input_text", "")
    with node_span("intent_router", turn_id=state.get("turn_id")):
        result = await deps.classifier.classify(
            text=text, history=_history(state), locale=state.get("locale", "es-MX")
        )

    intent = result.intent
    profile_filtered = result.profile_filtered
    if (
        intent is Intent.PRODUCT_DISCOVER
        and result.confidence < _ADVISORY_BIAS_THRESHOLD
        and result.runner_up is Intent.ADVISORY_RECOMMEND
    ):
        log.info("router.biased_to_advisory", confidence=result.confidence)
        intent = Intent.ADVISORY_RECOMMEND
        profile_filtered = True
    if intent is Intent.PRODUCT_DISCOVER and profile_filtered:
        # Profile-matched discovery is a regulated advisory act (DCGSI §1).
        intent = Intent.ADVISORY_RECOMMEND

    service_type = "asesorado" if intent in ADVISORY_INTENTS else "no_asesorado"
    update: dict[str, Any] = {
        "intent": intent,
        "intent_confidence": result.confidence,
        "intent_runner_up": result.runner_up,
        "profile_filtered": profile_filtered,
        "service_type": service_type,
        "service_subtype": SERVICE_SUBTYPE.get(intent, "informacion"),
        "degraded_from": None,
        "model_meta": {
            **state.get("model_meta", {}),
            "router": {
                "model": result.model,
                "confidence": result.confidence,
                "runner_up": str(result.runner_up) if result.runner_up else None,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        },
    }

    # Compliance-owned capability flags (ADR-0015).
    if intent in ADVISORY_INTENTS and not await deps.flags.is_on(
        "advisor.intent.advisory_recommend"
    ):
        degraded = _DEGRADATION[intent]
        log.info("router.advisory_flag_off", from_=str(intent), to=str(degraded))
        get_metrics().turns.add(1, {"event": "degradation", "reason": "flag"})
        update.update(
            {
                "intent": degraded,
                "degraded_from": intent,
                "service_type": "no_asesorado",
                "service_subtype": SERVICE_SUBTYPE[degraded],
            }
        )
    if intent in TRANSACTIONAL_INTENTS and not await deps.flags.is_on(
        "advisor.intent.transactional"
    ):
        update["error"] = AgentError(
            code="TRANSACTIONAL_DISABLED", message_es=TRANSACTIONAL_DISABLED_ES, escalate=True
        )
    return update


async def entitlement_gate(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    """Enforce contractual and profile preconditions before anything is said."""
    if state.get("error") is not None:
        return {}
    intent = state["intent"]
    entitlements = state["entitlements"]
    update: dict[str, Any] = {}

    with node_span("entitlement_gate", turn_id=state.get("turn_id"), intent=str(intent)):
        if intent in ADVISORY_INTENTS and not entitlements.contracted_for_advised_services:
            if (degraded := _DEGRADATION.get(intent)) is not None:
                log.info("entitlement.degraded", from_=str(intent), to=str(degraded))
                get_metrics().turns.add(1, {"event": "degradation", "reason": "entitlement"})
                return {
                    "intent": degraded,
                    "degraded_from": intent,
                    "service_type": "no_asesorado",
                    "service_subtype": SERVICE_SUBTYPE[degraded],
                }
            return _refuse("NOT_ENTITLED_ADVISORY", NOT_ENTITLED_ADVISORY_ES)

        if intent in TRANSACTIONAL_INTENTS and not entitlements.contracted_for_execution:
            return _refuse("NOT_ENTITLED_EXECUTION", NOT_ENTITLED_EXECUTION_ES)

        if intent in ADVISORY_INTENTS or intent in TRANSACTIONAL_INTENTS:
            profile = await _load_profile(state, deps)
            if profile is None:
                if intent in ADVISORY_INTENTS:
                    # Profile unavailable: advisory fails closed (docs/01-architecture/01 §8).
                    return _refuse("PROFILE_UNAVAILABLE", PROFILE_UNAVAILABLE_ES)
            else:
                update["investor_profile"] = profile
                if intent in ADVISORY_INTENTS and not profile.is_current(datetime.now(UTC).date()):
                    get_metrics().turns.add(1, {"event": "profile_expired"})
                    return {**update, **_refuse("PROFILE_EXPIRED", PROFILE_EXPIRED_ES)}
    return update


async def _load_profile(state: AdvisorState, deps: Dependencies) -> InvestorProfile | None:
    if (existing := state.get("investor_profile")) is not None:
        return existing
    result = await deps.gateway.call("get_investor_profile", client_id=state["client_id"], args={})
    if not result.ok or not isinstance(result.data, dict):
        log.warning("entitlement.profile_unavailable", error=result.error)
        return None
    payload = {k: v for k, v in result.data.items() if k != "as_of"}
    try:
        return InvestorProfile.model_validate(payload)
    except ValueError as exc:
        # An unknown enum value fails closed (docs/07-data-governance/03 §6).
        log.error("entitlement.profile_invalid", reason=type(exc).__name__)
        return None


def _refuse(code: str, message_es: str) -> dict[str, Any]:
    return {"error": AgentError(code=code, message_es=message_es, escalate=True)}
