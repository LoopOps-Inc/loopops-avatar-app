"""Transactional planning, suspension and post-execution nodes.

``transaction_planner`` produces a signed FormSpec and calls no mutating API
(ADR-0009, ADR-0010). ``await_form_submission`` suspends the run with
``interrupt``; the API layer resumes it with ``Command(resume=...)`` only after
``transaction-service`` has verified the step-up assertion and placed the order
(ADR-0017). ``execute_transaction`` then records the receipt for the second
evidence record. Nothing here moves money.
"""

from __future__ import annotations

from typing import Any

import structlog
from langgraph.types import interrupt

from actinver_agent.deps import Dependencies
from actinver_agent.graph.state import (
    AdvisorState,
    AgentError,
    Intent,
    Money,
    SuitabilityOutcome,
    UIComponent,
)
from actinver_agent.observability.setup import node_span
from actinver_agent.transactions.formspec import build_form_spec

log = structlog.get_logger(__name__)

REQUIREMENTS_UNAVAILABLE_ES = (
    "No pude preparar la operación en este momento. ¿Lo intentamos de nuevo o "
    "prefieres que te comunique con tu asesor?"
)
NOT_SUITABLE_FOR_BUY_ES = (
    "Ese producto no es congruente con tu perfil de inversionista, así que no "
    "puedo preparar la operación. Te comunico con tu asesor para buscar una alternativa."
)
FORM_READY_ES = (
    "Te preparé la operación. Revisa el monto, la cuenta y la fecha de liquidación "
    "en pantalla, y confírmala cuando estés listo."
)
RECEIPT_ES = (
    "Tu operación quedó registrada. El comprobante con el folio y la fecha de "
    "liquidación está en pantalla."
)

_SUITABILITY_REQUIRED: frozenset[Intent] = frozenset({Intent.TRANSACT_BUY, Intent.TRANSACT_SWITCH})


async def transaction_planner(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:
    if state.get("error") is not None:
        return {}
    if state.get("form_spec") is not None:
        return {}
    intent = state["intent"]
    results = state.get("tool_results", {})
    requirements = results.get("get_transaction_requirements")
    if requirements is None or not requirements.ok or not isinstance(requirements.data, dict):
        return {
            "error": AgentError(
                code="REQUIREMENTS_UNAVAILABLE",
                message_es=REQUIREMENTS_UNAVAILABLE_ES,
                escalate=True,
            )
        }

    verdict_id: str | None = None
    if intent in _SUITABILITY_REQUIRED:
        check = results.get("check_suitability")
        if check is None or not check.ok or not isinstance(check.data, dict):
            return {
                "error": AgentError(
                    code="SUITABILITY_UNAVAILABLE",
                    message_es=REQUIREMENTS_UNAVAILABLE_ES,
                    escalate=True,
                )
            }
        evaluations = check.data.get("evaluations", [])
        if any(e.get("outcome") == SuitabilityOutcome.NO_APTO for e in evaluations):
            return {
                "error": AgentError(
                    code="NO_SUITABLE_PRODUCT", message_es=NOT_SUITABLE_FOR_BUY_ES, escalate=True
                )
            }
        verdict_id = check.data.get("verdict_id")

    data = dict(requirements.data)
    disclosure_entries = data.get("disclosures", [])
    ids = [d["id"] for d in disclosure_entries if isinstance(d, dict) and d.get("id")]
    data["ack_ids"] = [d["id"] for d in disclosure_entries if isinstance(d, dict) and d.get("ack")]
    try:
        texts = await deps.guardrail.disclosure_texts(ids)
    except Exception as exc:
        log.error("transaction.disclosures_unavailable", reason=type(exc).__name__)
        return {
            "error": AgentError(
                code="GUARDRAIL_UNAVAILABLE", message_es=REQUIREMENTS_UNAVAILABLE_ES, escalate=True
            )
        }
    if set(texts) != set(ids):
        log.error("transaction.disclosure_missing", missing=sorted(set(ids) - set(texts)))
        return {
            "error": AgentError(
                code="GUARDRAIL_UNAVAILABLE", message_es=REQUIREMENTS_UNAVAILABLE_ES, escalate=True
            )
        }

    approved_amount: Money | None = state.get("proposed_amount")
    with node_span(
        "transaction_planner", turn_id=state.get("turn_id"), operation=data.get("operation")
    ):
        spec = build_form_spec(
            requirements=data,
            client_id=state["client_id"],
            thread_id=state["thread_id"],
            turn_id=state["turn_id"],
            suitability_verdict_id=verdict_id,
            approved_amount=approved_amount,
            disclosure_texts=texts,
            key=deps.form_signing_key,
            key_version=deps.form_signing_key_version,
            ttl_s=deps.settings.limits.form_ttl_s,
        )
        await deps.repos.form_specs.store(spec, status="ISSUED")
        writer = getattr(deps.audit, "writer", None)
        if writer is not None and hasattr(writer, "write_formspec_copy"):
            try:
                await writer.write_formspec_copy(spec.model_dump(mode="json"))
            except Exception as exc:
                log.warning("transaction.formspec_copy_failed", reason=type(exc).__name__)

    log.info(
        "transaction.form_prepared",
        form_id=spec.form_id,
        operation=spec.operation,
        turn_id=state.get("turn_id"),
    )
    speech = state.get("speech") or FORM_READY_ES
    return {
        "form_spec": spec,
        "speech": speech,
        "disclosures_shown": {
            **state.get("disclosures_shown", {}),
            **{d.id: d.version for d in spec.disclosures},
        },
    }


async def await_form_submission(state: AdvisorState) -> dict[str, Any]:
    """Suspend until the client confirms. The resume payload is produced by the
    API layer after transaction-service executed; it is never model output."""
    spec = state.get("form_spec")
    payload = interrupt(
        {
            "form_id": spec.form_id if spec else None,
            "expires_at": spec.expires_at.isoformat() if spec else None,
        }
    )
    if not isinstance(payload, dict) or payload.get("cancelled"):
        log.info("transaction.form_cancelled", form_id=spec.form_id if spec else None)
        return {"form_spec": None, "submission": None, "receipt": None, "error": None}
    return {
        "submission": dict(payload.get("submission") or {}),
        "receipt": dict(payload.get("receipt") or {}),
    }


async def execute_transaction(state: AdvisorState, deps: Dependencies) -> dict[str, Any]:  # noqa: ARG001
    """Resumed after a verified submission. Execution already happened in
    ``transaction-service``; this node records the receipt for the evidence
    chain (recommendation → verdict → form → step-up → order)."""
    receipt = state.get("receipt") or {}
    spec = state.get("form_spec")
    if not receipt or spec is None:
        return {}
    with node_span(
        "execute_transaction", turn_id=state.get("turn_id"), order_id=receipt.get("order_id")
    ):
        ui = UIComponent(
            type="order_receipt",
            payload={
                "order_id": receipt.get("order_id"),
                "status": receipt.get("status"),
                "settlement_date": receipt.get("settlement_date"),
                "operation": spec.operation,
                "product": spec.product.model_dump(mode="json"),
                "form_id": spec.form_id,
                "suitability_verdict_id": receipt.get("suitability_verdict_id")
                or spec.suitability_verdict_id,
            },
            source="service:transaction",
        )
    log.info("transaction.executed", order_id=receipt.get("order_id"), turn_id=state.get("turn_id"))
    return {
        "speech": RECEIPT_ES,
        "ui_payload": [ui],
        "citations": list(state.get("citations", [])),
        "error": None,
        "service_type": "no_asesorado",
        "service_subtype": "ejecucion_de_operaciones",
    }
