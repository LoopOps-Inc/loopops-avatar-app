"""Form submission (docs/04-backend/04 §2, docs/01-architecture/03 §5).

Nothing in the request body is trusted. The server re-verifies the spec
signature and TTL, checks the form belongs to this client and is unused,
re-enters the suitability gate when the amount changed, and hands execution to
``transaction-service``, which re-derives every limit and verifies the step-up
signature itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import structlog
from fastapi import APIRouter, Depends

from actinver_agent.api.routes.threads import owned_thread
from actinver_agent.api.schemas import FormSubmitRequest, FormSubmitResponse
from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import (
    IdempotencyGuard,
    get_deps,
    idempotency_key,
    require_client,
)
from actinver_agent.deps import Dependencies
from actinver_agent.errors import ApiError, api_error
from actinver_agent.graph.state import (
    FormSpec,
    InvestorProfile,
    Money,
    ProductProfile,
    SuitabilityOutcome,
    UIComponent,
)
from actinver_agent.ports import EvaluationInput

router = APIRouter(prefix="/v1", tags=["forms"])
log = structlog.get_logger(__name__)


def _verify_signature(spec: FormSpec, key: bytes) -> bool:
    from actinver_agent.transactions.formspec import verify_form_spec

    return bool(verify_form_spec(spec, key))


def _amount_from_values(values: dict[str, Any]) -> Money | None:
    raw = values.get("amount")
    if raw is None:
        return None
    if isinstance(raw, dict):
        return Money.model_validate(raw)
    if isinstance(raw, (int, float)):
        # Bare numbers are rejected: money always carries a currency.
        raise api_error("VALIDATION_ERROR", detail="amount must be {amount, currency}")
    try:
        Decimal(str(raw))
    except InvalidOperation as exc:
        raise api_error("VALIDATION_ERROR", detail="amount") from exc
    raise api_error("VALIDATION_ERROR", detail="amount must be {amount, currency}")


async def reevaluate_amount(
    deps: Dependencies, ctx: RequestContext, spec: FormSpec, amount: Money
) -> str:
    """A verdict is for an amount, not just a product (docs/01-architecture/03 §5.1)."""
    profile_raw = await deps.core.get_investor_profile(client_id=ctx.client_id)
    product_raw = await deps.core.get_product_profile(product_id=spec.product.id)
    positions = await deps.core.get_positions(client_id=ctx.client_id)
    limits = await deps.core.get_diversification_limits()
    profile = InvestorProfile.model_validate(
        {k: v for k, v in profile_raw.get("profile", profile_raw).items() if k != "as_of"}
    )
    product = ProductProfile.model_validate(
        {k: v for k, v in product_raw.get("profile", product_raw).items() if k != "as_of"}
    )
    total = Decimal(str((positions.get("total_value") or {}).get("amount", "0")))
    ctx_input = EvaluationInput(
        today=datetime.now(UTC),
        amount=amount.decimal,
        portfolio_total=total,
        current_weight_by_product={
            str(p.get("product_id")): float(p.get("weight", 0.0))
            for p in positions.get("positions", [])
        },
        current_weight_by_asset_class=dict(positions.get("weights_by_asset_class", {})),
        liquid_pct=float(positions.get("liquid_pct", 0.0)),
        diversification_limits=limits,
    )
    report = await deps.suitability.evaluate(
        client_id=ctx.client_id, profile=profile, products=[product], ctx=ctx_input
    )
    evaluation = report.evaluations[0]
    if evaluation.outcome is SuitabilityOutcome.NO_APTO:
        raise ApiError(
            status=422,
            code="NO_SUITABLE_PRODUCT",
            message_es=(
                "Con ese monto la operación no es congruente con tu perfil de inversionista. "
                f"{evaluation.rationale} Te comunico con tu asesor si lo prefieres."
            ),
            detail=evaluation.rule_id,
        )
    return report.verdict_id


@router.post(
    "/threads/{thread_id}/forms/{form_id}/submit",
    response_model=FormSubmitResponse,
    summary="Submit a Form Spec with a step-up assertion",
    description=(
        "Requires `Idempotency-Key`. The server re-verifies the spec signature and TTL, "
        "re-enters the suitability gate if the amount changed, verifies the step-up signature "
        "against the registered device key and only then places the order. Errors: "
        "`FORM_EXPIRED` 409, `FORM_SIGNATURE_INVALID` 400, `FORM_ALREADY_USED` 409, "
        "`ACK_REQUIRED` 422, `STEP_UP_REQUIRED` 401, `LIMIT_EXCEEDED` 422, `NO_SUITABLE_PRODUCT` 422."
    ),
)
async def submit_form(
    thread_id: str,
    form_id: str,
    body: FormSubmitRequest,
    ctx: RequestContext = Depends(require_client),
    key: str = Depends(idempotency_key),
    deps: Dependencies = Depends(get_deps),
) -> FormSubmitResponse:
    await owned_thread(deps, ctx, thread_id)
    if ctx.restricted:
        raise api_error("FORBIDDEN", detail="restricted device mode: transactions disabled")
    guard = IdempotencyGuard(
        deps, key=key, client_id=ctx.client_id, payload=body.model_dump(mode="json")
    )
    if (replay := await guard.replay()) is not None:
        return FormSubmitResponse.model_validate(replay)

    stored = await deps.repos.form_specs.get(form_id)
    if stored is None:
        raise api_error("NOT_FOUND", detail="form")
    spec, status = stored
    if spec.thread_id != thread_id:
        raise api_error("NOT_FOUND", detail="form")
    if not _verify_signature(spec, deps.form_signing_key):
        log.error("form.signature_invalid", form_id=form_id)
        raise api_error("FORM_SIGNATURE_INVALID")
    if spec.client_id != ctx.client_id:
        raise api_error("FORM_CLIENT_MISMATCH")
    if status != "ISSUED":
        raise api_error("FORM_ALREADY_USED")
    if spec.expires_at < datetime.now(UTC):
        await deps.repos.form_specs.mark(form_id, status="EXPIRED")
        raise api_error("FORM_EXPIRED")

    missing = [d for d in spec.required_acknowledgements() if d not in body.acknowledgements]
    if missing:
        raise api_error("ACK_REQUIRED", detail=",".join(missing))

    verdict_id = spec.suitability_verdict_id
    amount = _amount_from_values(body.values)
    if (
        amount is not None
        and spec.approved_amount is not None
        and (
            amount.decimal != spec.approved_amount.decimal
            or amount.currency != spec.approved_amount.currency
        )
    ):
        verdict_id = await reevaluate_amount(deps, ctx, spec, amount)

    try:
        receipt = await deps.transactions.execute(
            client_id=ctx.client_id,
            form_spec=spec,
            values=body.values,
            acknowledgements=body.acknowledgements,
            step_up_assertion=body.step_up_assertion,
            challenge_id=body.challenge_id,
            idempotency_key=f"{ctx.client_id}:{key}",
            suitability_verdict_id=verdict_id,
            jkt=ctx.jkt,
            device_id=ctx.device_id,
        )
    except ApiError:
        raise
    except Exception as exc:
        code = getattr(exc, "api_code", None)
        if code:
            raise api_error(str(code), detail=getattr(exc, "detail", None)) from exc
        log.exception("form.execute_failed")
        raise api_error("SERVICE_UNAVAILABLE", detail="transaction-service") from exc

    await deps.repos.form_specs.mark(form_id, status="USED")
    await deps.repos.form_specs.record_submission(
        form_id=form_id,
        client_id=ctx.client_id,
        values=body.values,
        acknowledgements=body.acknowledgements,
        disclosure_versions={d.id: d.version for d in spec.disclosures},
        step_up_challenge_id=body.challenge_id,
        order_id=receipt.order_id,
        idempotency_key=key,
    )

    speech: str | None = None
    ui: list[UIComponent] = []
    evidence_id = receipt.evidence_id
    if deps.runner is not None:
        outcome = await deps.runner.resume_form(
            ctx,
            thread_id=thread_id,
            form_id=form_id,
            submission={
                "values": body.values,
                "acknowledgements": body.acknowledgements,
                "challenge_id": body.challenge_id,
            },
            receipt={
                "order_id": receipt.order_id,
                "status": receipt.status,
                "settlement_date": receipt.settlement_date,
                "suitability_verdict_id": verdict_id,
            },
        )
        speech = outcome.speech
        ui = [UIComponent.model_validate(c) for c in outcome.ui_payload]
        evidence_id = outcome.evidence_id or evidence_id

    response = FormSubmitResponse(
        order_id=receipt.order_id,
        status=receipt.status,
        settlement_date=receipt.settlement_date,
        evidence_id=evidence_id,
        ui_payload=ui,
        speech=speech,
    )
    await guard.store(response.model_dump(mode="json"))
    return response
