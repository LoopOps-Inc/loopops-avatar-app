"""Compliance console, flags, incident-response hooks and ARCO
(docs/06-compliance/02 §7, 05-security/06, 06-compliance/04 §6, ADR-0015).

Every read of evidence is logged to a separate audit trail (control EV-05) and
requires a stated business reason (``X-Reason`` header). Queries are scoped,
never bulk.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import orjson
import structlog
from fastapi import APIRouter, Depends, Header, Query, status

from actinver_agent.api.schemas import (
    ArcoRequest,
    ArcoResponse,
    ChainVerifyResponse,
    ComplianceSummary,
    EvidenceListItem,
    EvidenceListResponse,
    FlagUpdateRequest,
    FlagView,
    RevokeSessionsRequest,
)
from actinver_agent.auth.context import (
    ROLE_COMPLIANCE,
    ROLE_RISK,
    ROLE_SECURITY,
    ROLE_SRE,
    RequestContext,
)
from actinver_agent.auth.dependencies import get_deps, require_role
from actinver_agent.auth.jwt import revoke_client
from actinver_agent.deps import Dependencies
from actinver_agent.errors import api_error
from actinver_agent.flags import FLAG_INDEX, FLAGS
from actinver_agent.graph.state import ConsentType
from actinver_agent.observability.setup import client_hash

router = APIRouter(prefix="/v1/compliance", tags=["compliance"])
log = structlog.get_logger(__name__)

_FLAG_AUTHORITY: dict[str, tuple[str, ...]] = {
    "Compliance": (ROLE_COMPLIANCE,),
    "Risk": (ROLE_RISK, ROLE_SRE),
    "Product": (ROLE_COMPLIANCE, ROLE_RISK, ROLE_SRE),
    "Engineering": (ROLE_SRE, ROLE_RISK),
}


def reason_header(
    x_reason: str = Header(..., alias="X-Reason", min_length=3, max_length=500),
) -> str:
    return x_reason


async def _log_access(
    deps: Dependencies, ctx: RequestContext, action: str, scope: dict[str, Any], reason: str
) -> None:
    await deps.repos.access_log.log(actor=ctx.client_id, action=action, scope=scope, reason=reason)


# ── Evidence ───────────────────────────────────────────────────────────────────


@router.get(
    "/evidence",
    response_model=EvidenceListResponse,
    summary="Query the evidence index (scoped, never bulk)",
    description=(
        "Requires role `compliance`, `security` or `risk` and an `X-Reason` header. At least one "
        "of `client_id`, `thread_id` or a `since`/`until` window is required. Access is logged."
    ),
)
async def list_evidence(
    client_id: str | None = Query(default=None),
    thread_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    service_type: str | None = Query(default=None),
    product_id: str | None = Query(default=None),
    refused: bool | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    reason: str = Depends(reason_header),
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE, ROLE_SECURITY, ROLE_RISK)),
    deps: Dependencies = Depends(get_deps),
) -> EvidenceListResponse:
    if not (client_id or thread_id or (since and until)):
        raise api_error(
            "VALIDATION_ERROR", detail="scope the query by client_id, thread_id or a window"
        )
    scope = {
        "client_id": client_id,
        "thread_id": thread_id,
        "since": since,
        "until": until,
        "service_type": service_type,
        "product_id": product_id,
        "refused": refused,
    }
    await _log_access(deps, ctx, "evidence.query", scope, reason)
    rows, next_cursor = await deps.repos.evidence_index.query(
        client_id=client_id,
        thread_id=thread_id,
        since=since,
        until=until,
        service_type=service_type,
        product_id=product_id,
        refused=refused,
        limit=limit,
        cursor=cursor,
    )
    return EvidenceListResponse(
        items=[
            EvidenceListItem(
                evidence_id=r.evidence_id,
                client_hash=client_hash(r.client_id),
                thread_id=r.thread_id,
                turn_id=r.turn_id,
                created_at=r.created_at,
                service_type=r.service_type,
                service_subtype=r.service_subtype,
                intent=r.intent,
                product_ids=r.product_ids,
                content_hash=r.content_hash,
                legal_hold=r.legal_hold,
                refused=r.refused,
            )
            for r in rows
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/evidence/verify/{thread_id}",
    response_model=ChainVerifyResponse,
    summary="Re-walk a thread's hash chain",
    description="Any divergence is a security incident (control EV-02).",
)
async def verify_chain(
    thread_id: str,
    reason: str = Depends(reason_header),
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE, ROLE_SECURITY)),
    deps: Dependencies = Depends(get_deps),
) -> ChainVerifyResponse:
    await _log_access(deps, ctx, "evidence.verify", {"thread_id": thread_id}, reason)
    verifier = getattr(deps.audit, "verify_thread", None)
    if verifier is None:
        raise api_error("SERVICE_UNAVAILABLE", detail="chain verification not available")
    ok, records, divergent = await verifier(thread_id)
    return ChainVerifyResponse(
        thread_id=thread_id, ok=ok, records=records, first_divergent_evidence_id=divergent
    )


@router.get(
    "/evidence/{evidence_id}",
    summary="Read one evidence record",
    description="Returns the raw WORM record. Requires `X-Reason`; access is logged.",
)
async def get_evidence(
    evidence_id: str,
    reason: str = Depends(reason_header),
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE, ROLE_SECURITY, ROLE_RISK)),
    deps: Dependencies = Depends(get_deps),
) -> dict[str, Any]:
    row = await deps.repos.evidence_index.get(evidence_id)
    if row is None:
        raise api_error("NOT_FOUND", detail="evidence")
    await _log_access(
        deps, ctx, "evidence.read", {"evidence_id": evidence_id, "thread_id": row.thread_id}, reason
    )
    body = await deps.object_store.get(row.object_key)
    if body is None:
        raise api_error("NOT_FOUND", detail="evidence object")
    return dict(orjson.loads(body))


@router.get(
    "/summary",
    response_model=ComplianceSummary,
    summary="Supervision summary for a window",
    description="Turn volumes by service type, suitability outcomes, guardrail blocks, escalations, degradations, model/prompt versions.",
)
async def summary(
    since: datetime = Query(...),
    until: datetime = Query(...),
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE, ROLE_RISK)),
    deps: Dependencies = Depends(get_deps),
) -> ComplianceSummary:
    counts = await deps.repos.evidence_index.counts(since=since, until=until)
    return ComplianceSummary(
        window={"since": since, "until": until},
        turns_by_service_type=dict(counts.get("turns_by_service_type", {})),
        suitability_outcomes=dict(counts.get("suitability_outcomes", {})),
        guardrail_blocks_by_reason=dict(counts.get("guardrail_blocks_by_reason", {})),
        escalations=int(counts.get("escalations", 0)),
        degradations=int(counts.get("degradations", 0)),
        refusals=int(counts.get("refusals", 0)),
        evidence_records=int(counts.get("evidence_records", 0)),
        model_versions=dict(counts.get("model_versions", {})),
        prompt_versions=dict(counts.get("prompt_versions", {})),
    )


# ── Flags ──────────────────────────────────────────────────────────────────────


@router.get(
    "/flags", response_model=list[FlagView], summary="Feature flag inventory and live values"
)
async def list_flags(
    ctx: RequestContext = Depends(
        require_role(ROLE_COMPLIANCE, ROLE_RISK, ROLE_SRE, ROLE_SECURITY)
    ),
    deps: Dependencies = Depends(get_deps),
) -> list[FlagView]:
    return [
        FlagView(
            name=f.name,
            value=await deps.flags.get(f.name),
            default=f.default,
            owner=f.owner,
            expires_at=f.expires_at.isoformat(),
        )
        for f in FLAGS
    ]


@router.put(
    "/flags/{name}",
    response_model=FlagView,
    summary="Change a flag without a deploy",
    description=(
        "Authority follows the flag owner: Compliance flags → role `compliance`; "
        "`advisor.kill_switch` → `risk` (or the on-call `sre`); Product/Engineering flags → "
        "`compliance`, `risk` or `sre`. The reason is logged. Propagates in under 30 s."
    ),
)
async def set_flag(
    name: str,
    body: FlagUpdateRequest,
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE, ROLE_RISK, ROLE_SRE)),
    deps: Dependencies = Depends(get_deps),
) -> FlagView:
    spec = FLAG_INDEX.get(name)
    if spec is None:
        raise api_error("NOT_FOUND", detail="flag")
    allowed = _FLAG_AUTHORITY.get(spec.owner, (ROLE_RISK,))
    if not any(ctx.has_role(r) for r in allowed):
        raise api_error("FORBIDDEN", detail=f"flag owned by {spec.owner}")
    await deps.flags.set(name, body.value, actor=ctx.client_id)
    await deps.repos.access_log.log(
        actor=ctx.client_id,
        action="flag.set",
        scope={"flag": name, "value": body.value},
        reason=body.reason,
    )
    if name == "advisor.kill_switch" and body.value.lower() in {"on", "true", "1"} and deps.broker:
        # Kill switch: tear down avatar sessions immediately (RB-07 step 2).
        await deps.broker.stop_all(reason="kill_switch")
    return FlagView(
        name=name,
        value=await deps.flags.get(name),
        default=spec.default,
        owner=spec.owner,
        expires_at=spec.expires_at.isoformat(),
    )


# ── Incident response ──────────────────────────────────────────────────────────


@router.post(
    "/sessions/revoke",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Revoke sessions for a cohort",
    description="Rejects tokens issued before `issued_before` (default now) for each client and stops their avatar sessions.",
)
async def revoke_sessions(
    body: RevokeSessionsRequest,
    ctx: RequestContext = Depends(require_role(ROLE_SECURITY, ROLE_RISK)),
    deps: Dependencies = Depends(get_deps),
) -> dict[str, int]:
    if not body.client_ids:
        raise api_error("VALIDATION_ERROR", detail="client_ids required")
    stopped = 0
    for client_id in body.client_ids:
        await revoke_client(deps.cache, client_id, issued_before=body.issued_before)
        if deps.broker is not None:
            stopped += await deps.broker.stop_all_for_client(client_id, reason="revoked")
    await deps.repos.access_log.log(
        actor=ctx.client_id,
        action="sessions.revoke",
        scope={"count": len(body.client_ids)},
        reason=body.reason,
    )
    return {"revoked_clients": len(body.client_ids), "avatar_sessions_stopped": stopped}


async def _set_freeze(
    deps: Dependencies, ctx: RequestContext, thread_id: str, *, on: bool, reason: str
) -> dict[str, Any]:
    thread = await deps.repos.threads.get(thread_id)
    if thread is None:
        raise api_error("NOT_FOUND", detail="thread")
    await deps.repos.threads.set_frozen(thread_id, frozen=on)
    held = await deps.repos.evidence_index.set_legal_hold(thread_id=thread_id, on=on)
    rows, _ = await deps.repos.evidence_index.query(
        client_id=None,
        thread_id=thread_id,
        since=None,
        until=None,
        service_type=None,
        product_id=None,
        refused=None,
        limit=1000,
        cursor=None,
    )
    for row in rows:
        await deps.object_store.set_legal_hold(row.object_key, on=on)
    await deps.repos.access_log.log(
        actor=ctx.client_id,
        action="thread.freeze" if on else "thread.unfreeze",
        scope={"thread_id": thread_id, "records": held},
        reason=reason,
    )
    return {"thread_id": thread_id, "frozen": on, "legal_hold_records": held}


@router.post(
    "/threads/{thread_id}/freeze", summary="Freeze a thread and place its evidence under legal hold"
)
async def freeze_thread(
    thread_id: str,
    reason: str = Depends(reason_header),
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE, ROLE_SECURITY)),
    deps: Dependencies = Depends(get_deps),
) -> dict[str, Any]:
    return await _set_freeze(deps, ctx, thread_id, on=True, reason=reason)


@router.post(
    "/threads/{thread_id}/unfreeze",
    summary="Lift a thread freeze (dual authorisation is a process control)",
)
async def unfreeze_thread(
    thread_id: str,
    reason: str = Depends(reason_header),
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE, ROLE_SECURITY)),
    deps: Dependencies = Depends(get_deps),
) -> dict[str, Any]:
    return await _set_freeze(deps, ctx, thread_id, on=False, reason=reason)


# ── ARCO ───────────────────────────────────────────────────────────────────────

RETAINED_CATEGORIES_ES: list[dict[str, str]] = [
    {
        "category": "Registros de evidencia de cada conversación",
        "retention": "5 años",
        "basis": "DCGSI Art. 26",
    },
    {"category": "Transcripciones", "retention": "5 años", "basis": "DCGSI Art. 26"},
    {
        "category": "Grabaciones de voz (cliente y asistente)",
        "retention": "5 años",
        "basis": "DCGSI Art. 26",
    },
    {
        "category": "Formularios de operación y confirmaciones",
        "retention": "5 años",
        "basis": "DCGSI Art. 26",
    },
    {
        "category": "Registros de consentimiento",
        "retention": "relación + 5 años",
        "basis": "LFPDPPP y DCGSI",
    },
]

RETAINED_STATEMENT_ES = (
    "Las grabaciones y registros de tus conversaciones con el asistente se conservan cinco años "
    "conforme a la normativa aplicable a los servicios de inversión (DCGSI Art. 26) y no pueden "
    "cancelarse antes de ese plazo. Los datos que no están sujetos a esa obligación (por ejemplo, "
    "el uso de conversaciones seudonimizadas para mejorar el asistente) se eliminan con esta solicitud."
)


async def _export_bundle(deps: Dependencies, client_id: str) -> dict[str, Any]:
    threads = await deps.repos.threads.list_for_client(client_id)
    turns: list[dict[str, Any]] = []
    for thread in threads:
        cursor: str | None = None
        while True:
            page, cursor = await deps.repos.threads.list_turns(
                thread_id=thread.thread_id, cursor=cursor, limit=200
            )
            turns.extend(
                {
                    "thread_id": t.thread_id,
                    "turn_id": t.turn_id,
                    "created_at": t.created_at,
                    "channel": t.channel,
                    "client_text": t.client_text,
                    "speech": t.speech,
                    "ui_payload": t.ui_payload,
                    "evidence_id": t.evidence_id,
                    "service_type": t.service_type,
                    "intent": t.intent,
                }
                for t in page
            )
            if cursor is None:
                break
    consents = await deps.repos.consents.list_for_client(client_id)
    rows, _ = await deps.repos.evidence_index.query(
        client_id=client_id,
        thread_id=None,
        since=None,
        until=None,
        service_type=None,
        product_id=None,
        refused=None,
        limit=1000,
        cursor=None,
    )
    evidence: list[dict[str, Any]] = []
    for row in rows:
        body = await deps.object_store.get(row.object_key)
        evidence.append(
            orjson.loads(body) if body else {"evidence_id": row.evidence_id, "missing": True}
        )
    return {
        "schema_version": "1.0",
        "client_id": client_id,
        "generated_at": datetime.now(UTC),
        "threads": [
            {
                "thread_id": t.thread_id,
                "channel": t.channel,
                "created_at": t.created_at,
                "turn_count": t.turn_count,
            }
            for t in threads
        ],
        "turns": turns,
        "consents": [c.model_dump(mode="json") for c in consents],
        "evidence_records": evidence,
        "retained_categories": RETAINED_CATEGORIES_ES,
    }


@router.post(
    "/arco",
    response_model=ArcoResponse,
    summary="Open and fulfil a data-subject (ARCO) request",
    description=(
        "`acceso`/`portabilidad`: machine-readable JSON export written to the object store under "
        "`exports/dsr/{request_id}/` with a 90-day expiry and a presigned URL. `cancelacion`: "
        "revokes the model-improvement consent and returns the retained-data statement (evidence "
        "under DCGSI Art. 26 is retained). `rectificacion`: appends a correction note, never rewrites. "
        "`oposicion`: revokes non-necessary purposes. Every request is logged with timestamps for the 20-day SLA."
    ),
)
async def arco(
    body: ArcoRequest,
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE)),
    deps: Dependencies = Depends(get_deps),
) -> ArcoResponse:
    request_id = f"dsr_{uuid.uuid4().hex[:16]}"
    opened_at = datetime.now(UTC)
    await deps.repos.arco.open_request(
        request_id=request_id, client_id=body.client_id, kind=body.kind, opened_at=opened_at
    )
    await deps.repos.access_log.log(
        actor=ctx.client_id,
        action=f"arco.{body.kind}",
        scope={"request_id": request_id, "client_id": body.client_id},
        reason=body.reason,
    )
    response = ArcoResponse(request_id=request_id, kind=body.kind, opened_at=opened_at)
    export_key: str | None = None
    now = datetime.now(UTC)

    if body.kind in ("acceso", "portabilidad"):
        bundle = await _export_bundle(deps, body.client_id)
        export_key = f"exports/dsr/{request_id}/export.json"
        expires_at = now + timedelta(days=90)
        await deps.object_store.put_expiring(
            export_key,
            orjson.dumps(bundle, default=str),
            expires_at=expires_at,
            content_type="application/json",
        )
        response.export_url = await deps.object_store.presign_get(export_key, ttl_s=24 * 3600)
        response.export_expires_at = expires_at
    elif body.kind in ("cancelacion", "oposicion"):
        await deps.repos.consents.revoke(
            client_id=body.client_id, type=ConsentType.MODEL_IMPROVEMENT, at=now
        )
        response.retained_data_statement_es = RETAINED_STATEMENT_ES
        response.retained_categories = RETAINED_CATEGORIES_ES
    elif body.kind == "rectificacion":
        export_key = f"exports/dsr/{request_id}/correction.json"
        note = {
            "request_id": request_id,
            "client_id": body.client_id,
            "kind": "rectificacion",
            "note": body.reason,
            "appended_at": now,
            "statement": "Los registros de evidencia no se reescriben; esta corrección se anexa.",
        }
        await deps.object_store.put_immutable(
            export_key,
            orjson.dumps(note, default=str),
            retain_until=now + timedelta(days=365 * deps.settings.object_store.retention_years),
            content_type="application/json",
        )
        response.retained_data_statement_es = RETAINED_STATEMENT_ES

    await deps.repos.arco.close_request(
        request_id=request_id, closed_at=datetime.now(UTC), export_key=export_key
    )
    return response


@router.get("/arco", summary="ARCO request log with response times")
async def list_arco(
    client_id: str | None = Query(default=None),
    ctx: RequestContext = Depends(require_role(ROLE_COMPLIANCE)),
    deps: Dependencies = Depends(get_deps),
) -> list[dict[str, Any]]:
    return await deps.repos.arco.list_requests(client_id=client_id)
