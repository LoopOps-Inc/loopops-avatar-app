"""Audit node. Fail-closed for advisory and transactional turns (ADR-0012).

Informational turns spool durably when the store is down; advisory,
transactional and asesorado-refusal turns produce no response without evidence.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from actinver_agent.audit.record import build_record
from actinver_agent.deps import Dependencies
from actinver_agent.graph.state import (
    ADVISORY_INTENTS,
    TRANSACTIONAL_INTENTS,
    AdvisorState,
    AgentError,
    UIComponent,
)
from actinver_agent.observability.setup import get_metrics, node_span

log = structlog.get_logger(__name__)

AUDIT_DOWN_ES = (
    "No puedo continuar en este momento por un problema técnico. Te comunico con tu asesor."
)


def must_succeed(state: AdvisorState) -> bool:
    intent = state.get("intent")
    return bool(
        intent in ADVISORY_INTENTS
        or intent in TRANSACTIONAL_INTENTS
        or state.get("service_type") == "asesorado"
        or state.get("degraded_from") is not None
        or state.get("receipt")
        or state.get("form_spec") is not None
    )


async def audit_sink(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    channel = state.get("channel", "chat")
    client_input = {
        "modality": "audio" if channel == "voice" else "text",
        "audio_ref": state.get("audio_ref"),
        "transcript": state.get("client_input_text"),
        "asr_confidence": state.get("transcript_confidence"),
        "language": state.get("locale", "es-MX"),
    }
    record = build_record(
        state,
        model_meta=state.get("model_meta") or None,
        prompt_version=deps.prompts.version,
        ruleset_version=deps.settings.suitability_ruleset_version,
        disclosures_shown=state.get("disclosures_shown") or {},
        client_input=client_input,
        audio_refs={"client": state.get("audio_ref"), "avatar": None},
        retention_years=deps.settings.object_store.retention_years,
    )
    fail_closed = must_succeed(state)
    started = time.perf_counter()
    with node_span("audit_sink", turn_id=state.get("turn_id"), fail_closed=fail_closed):
        try:
            result = await deps.audit.write(record=record, fail_closed=fail_closed)
        except Exception as exc:
            get_metrics().evidence_write_failures.add(1, {"fail_closed": str(fail_closed)})
            log.error(
                "audit.write_failed",
                reason=type(exc).__name__,
                fail_closed=fail_closed,
                turn_id=state.get("turn_id"),
            )
            if fail_closed:
                # No evidence, no response. This is the fail-closed rule.
                return {
                    "speech": AUDIT_DOWN_ES,
                    "ui_payload": [
                        UIComponent(
                            type="escalation_offer",
                            payload={
                                "reason": "AUDIT_UNAVAILABLE",
                                "cta_es": "Hablar con mi asesor",
                            },
                            source="system",
                        )
                    ],
                    "form_spec": None,
                    "citations": [],
                    "error": AgentError(
                        code="AUDIT_UNAVAILABLE", message_es=AUDIT_DOWN_ES, escalate=True
                    ),
                    "evidence_id": None,
                }
            return {"evidence_id": None}
    get_metrics().evidence_write_ms.record((time.perf_counter() - started) * 1000)
    log.info(
        "evidence.recorded",
        evidence_id=result.evidence_id,
        spooled=result.spooled,
        service_type=state.get("service_type"),
        turn_id=state.get("turn_id"),
    )
    return {"evidence_id": result.evidence_id}
