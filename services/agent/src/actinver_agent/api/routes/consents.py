"""Consents and disclosures (DCGSI Art. 24/26, LFPDPPP; docs/06-compliance/04 §3).

Two separately revocable consents (voice recording, model improvement) plus
three acknowledgements (privacy notice, services guide, AI disclosure). Every
record carries the version acknowledged and a timestamp.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Response, status

from actinver_agent.api.disclosure_docs import (
    CONSENT_REQUIRED_FOR,
    consent_text,
    current_version,
    public_id,
)
from actinver_agent.api.schemas import (
    ConsentAckRequest,
    ConsentsResponse,
    ConsentView,
    DisclosureText,
)
from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import (
    IdempotencyGuard,
    get_deps,
    idempotency_key,
    require_client,
)
from actinver_agent.deps import Dependencies
from actinver_agent.errors import api_error
from actinver_agent.graph.state import PUBLIC_ID_TO_CONSENT, ConsentRecord, ConsentType

router = APIRouter(prefix="/v1", tags=["consents"])
log = structlog.get_logger(__name__)


async def _views(deps: Dependencies, client_id: str) -> ConsentsResponse:
    records = await deps.repos.consents.list_for_client(client_id)
    views: list[ConsentView] = []
    for consent in ConsentType:
        version = current_version(deps.settings, consent)
        active = [r for r in records if r.type is consent and r.granted and r.revoked_at is None]
        latest = max(active, key=lambda r: r.granted_at) if active else None
        revoked = [r for r in records if r.type is consent and r.revoked_at is not None]
        views.append(
            ConsentView(
                type=consent,
                public_id=public_id(consent),
                current_version=version,
                granted=latest is not None and latest.version == version,
                granted_version=latest.version if latest else None,
                granted_at=latest.granted_at if latest else None,
                revoked_at=max(r.revoked_at for r in revoked if r.revoked_at)
                if revoked and not latest
                else None,
                required_for=CONSENT_REQUIRED_FOR[consent],
            )
        )
    return ConsentsResponse(consents=views)


@router.get(
    "/consents", response_model=ConsentsResponse, summary="Consent and acknowledgement state"
)
async def list_consents(
    ctx: RequestContext = Depends(require_client),
    deps: Dependencies = Depends(get_deps),
) -> ConsentsResponse:
    return await _views(deps, ctx.client_id)


@router.post(
    "/consents",
    response_model=ConsentsResponse,
    summary="Record an acknowledgement or consent",
    description=(
        "Requires `Idempotency-Key`. `version` must equal the current version of the document "
        "(see `GET /v1/consents`). `MODEL_IMPROVEMENT` is opt-in and off by default; it is never "
        "bundled with voice recording."
    ),
)
async def acknowledge(
    body: ConsentAckRequest,
    ctx: RequestContext = Depends(require_client),
    key: str = Depends(idempotency_key),
    deps: Dependencies = Depends(get_deps),
) -> ConsentsResponse:
    guard = IdempotencyGuard(
        deps, key=key, client_id=ctx.client_id, payload=body.model_dump(mode="json")
    )
    if (replay := await guard.replay()) is not None:
        return ConsentsResponse.model_validate(replay)
    expected = current_version(deps.settings, body.type)
    if body.version != expected:
        raise api_error("VALIDATION_ERROR", detail=f"version must be {expected}")
    await deps.repos.consents.record(
        ConsentRecord(
            client_id=ctx.client_id,
            type=body.type,
            version=body.version,
            granted=body.granted,
            granted_at=datetime.now(UTC),
            channel=body.channel,
        )
    )
    log.info(
        "consent.recorded", consent=body.type.value, version=body.version, granted=body.granted
    )
    response = await _views(deps, ctx.client_id)
    await guard.store(response.model_dump(mode="json"))
    return response


@router.delete(
    "/consents/{consent_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a consent",
    description=(
        "Revoking `voice_recording` stops any active avatar session immediately; chat mode "
        "remains fully available. Revoking `model_improvement` changes nothing functionally."
    ),
    response_class=Response,
)
async def revoke(
    consent_type: ConsentType,
    ctx: RequestContext = Depends(require_client),
    deps: Dependencies = Depends(get_deps),
) -> Response:
    revoked = await deps.repos.consents.revoke(
        client_id=ctx.client_id, type=consent_type, at=datetime.now(UTC)
    )
    if consent_type is ConsentType.VOICE_RECORDING and deps.broker is not None:
        await deps.broker.stop_all_for_client(ctx.client_id, reason="consent_revoked")
    log.info("consent.revoked", consent=consent_type.value, existed=revoked)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/disclosures/{disclosure_id}",
    response_model=DisclosureText,
    summary="Verbatim disclosure or consent text with its version",
    description=(
        "Accepts a consent document id (`PRIVACY_NOTICE`, `SERVICES_GUIDE`, `AI_ASSISTANT`, "
        "`VOICE_RECORDING`, `MODEL_IMPROVEMENT`) or a mandatory disclosure id "
        "(`PAST_PERF`, `NO_GUARANTEE`, `COSTS`, `NOT_A_RECOMMENDATION`, ...)."
    ),
)
async def disclosure(
    disclosure_id: str,
    deps: Dependencies = Depends(get_deps),
) -> DisclosureText:
    consent = PUBLIC_ID_TO_CONSENT.get(disclosure_id)
    if consent is not None:
        return DisclosureText(
            id=disclosure_id,
            version=current_version(deps.settings, consent),
            text=consent_text(consent),
        )
    texts = await deps.guardrail.disclosure_texts([disclosure_id])
    if disclosure_id not in texts:
        raise api_error("NOT_FOUND", detail="disclosure")
    text, version = texts[disclosure_id]
    return DisclosureText(id=disclosure_id, version=version, text=text)
