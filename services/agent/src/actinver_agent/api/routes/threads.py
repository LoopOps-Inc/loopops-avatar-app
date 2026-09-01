"""Chat turn (SSE) and thread history (docs/04-backend/04 §2, docs/01-architecture/03 §3).

SSE events, in order of appearance:

    event: token       data: {"text": "Tu portafolio "}
    event: ui          data: {"type": "portfolio_summary", "payload": {…}, "as_of": "…", "source": "tool:…"}
    event: form_spec   data: {"form_id": "fs_…", "fields": [...], "signature": "…", ...}
    event: citations   data: {"items": [...]}
    event: error       data: {"code": "BLOCKED_OUTPUT", "message": "…", "escalate": true}
    event: done        data: {"turn_id": "tn_…", "evidence_id": "ev_…", "service_type": "no_asesorado"}

``done`` always fires, including after ``error``. Guardrail refusals are
in-stream 200s, never HTTP errors.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import orjson
import structlog
from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from actinver_agent.api.disclosure_docs import current_version
from actinver_agent.api.schemas import (
    SendMessageRequest,
    SseEventCatalogue,
    ThreadResponse,
    ThreadTurn,
)
from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import get_deps, require_client
from actinver_agent.auth.ratelimit import RateLimiter
from actinver_agent.deps import Dependencies
from actinver_agent.errors import api_error
from actinver_agent.flags import KILL_SWITCH_MESSAGE_ES
from actinver_agent.graph.state import FIRST_TURN_CONSENTS, UIComponent
from actinver_agent.observability.setup import get_metrics
from actinver_agent.ports import ThreadRecord

router = APIRouter(prefix="/v1", tags=["threads"])
log = structlog.get_logger(__name__)


async def owned_thread(deps: Dependencies, ctx: RequestContext, thread_id: str) -> ThreadRecord:
    """404 for both unknown and foreign threads: never leak existence."""
    thread = await deps.repos.threads.get(thread_id)
    if thread is None or thread.client_id != ctx.client_id:
        raise api_error("NOT_FOUND", detail="thread")
    return thread


async def assert_first_turn_consents(deps: Dependencies, client_id: str) -> None:
    """The guide, the privacy notice and the AI disclosure gate the first turn (Art. 24)."""
    missing: list[str] = []
    for consent in FIRST_TURN_CONSENTS:
        ok = await deps.repos.consents.has_active(
            client_id=client_id, type=consent, version=current_version(deps.settings, consent)
        )
        if not ok:
            missing.append(consent.value)
    if missing:
        raise api_error("CONSENT_REQUIRED", detail=",".join(missing))


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": orjson.dumps(data, default=str).decode()}


@router.post(
    "/threads/{thread_id}/messages",
    summary="Send a chat message (SSE response)",
    description=(
        "Responds with `text/event-stream`. Events: `token`, `ui`, `form_spec`, `citations`, "
        "`error`, `done`. `done` always fires, including after `error`. Guardrail refusals "
        "(`BLOCKED_INPUT`, `BLOCKED_OUTPUT`, `NOT_ENTITLED_ADVISORY`, `NOT_ENTITLED_EXECUTION`, "
        "`PROFILE_EXPIRED`, `NO_SUITABLE_PRODUCT`, `LOW_CONFIDENCE`) arrive as in-stream "
        "`error` events with HTTP 200. See `GET /v1/docs/sse-events` for the JSON schema."
    ),
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "SSE stream"},
        403: {"description": "CONSENT_REQUIRED - first-turn disclosures not acknowledged"},
        404: {"description": "Unknown thread"},
        423: {"description": "THREAD_FROZEN"},
        429: {"description": "RATE_LIMITED"},
    },
)
async def send_message(
    thread_id: str,
    body: SendMessageRequest,
    ctx: RequestContext = Depends(require_client),
    deps: Dependencies = Depends(get_deps),
) -> EventSourceResponse:
    thread = await owned_thread(deps, ctx, thread_id)
    if thread.frozen:
        raise api_error("THREAD_FROZEN")
    if len(body.text) > deps.settings.limits.max_message_chars:
        raise api_error("MESSAGE_TOO_LONG")
    decision = await RateLimiter(deps.settings, deps.cache).check_turn(
        client_id=ctx.client_id, device=ctx.jkt or ctx.device_id
    )
    if not decision.allowed:
        get_metrics().rate_limited.add(1)
        raise api_error("RATE_LIMITED", retry_after_s=decision.retry_after_s)
    await assert_first_turn_consents(deps, ctx.client_id)

    if await deps.flags.kill_switch_active():
        get_metrics().kill_switch_refusals.add(1)

        async def killed() -> AsyncIterator[dict[str, str]]:
            yield _sse(
                "error",
                {"code": "KILL_SWITCH", "message": KILL_SWITCH_MESSAGE_ES, "escalate": True},
            )
            yield _sse(
                "ui",
                {
                    "type": "escalation_offer",
                    "payload": {"reason": "KILL_SWITCH", "cta_es": "Hablar con mi asesor"},
                    "source": "system",
                    "as_of": None,
                },
            )
            yield _sse(
                "done", {"turn_id": None, "evidence_id": None, "service_type": "no_asesorado"}
            )

        return EventSourceResponse(killed())

    runner = deps.runner
    if runner is None:
        raise api_error("SERVICE_UNAVAILABLE", detail="runner")

    async def stream() -> AsyncIterator[dict[str, str]]:
        done_sent = False
        try:
            async for event in runner.run_turn(
                ctx, thread_id=thread_id, text=body.text, channel="chat", locale=body.locale
            ):
                if event.kind in ("thinking", "filler"):
                    continue
                if event.kind == "done":
                    done_sent = True
                yield _sse(event.kind, event.data)
        except Exception:
            log.exception("chat.turn_failed")
            yield _sse(
                "error",
                {
                    "code": "SERVICE_UNAVAILABLE",
                    "message": "Ocurrió un problema técnico. Te comunico con tu asesor.",
                    "escalate": True,
                },
            )
        finally:
            if not done_sent:
                yield _sse(
                    "done", {"turn_id": None, "evidence_id": None, "service_type": "no_asesorado"}
                )

    return EventSourceResponse(
        stream(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get(
    "/threads/{thread_id}",
    response_model=ThreadResponse,
    summary="Thread history (cursor pagination)",
    description="Returns turns oldest-first. Pass `next_cursor` back as `cursor` for the next page.",
)
async def get_thread(
    thread_id: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: RequestContext = Depends(require_client),
    deps: Dependencies = Depends(get_deps),
) -> ThreadResponse:
    thread = await owned_thread(deps, ctx, thread_id)
    turns, next_cursor = await deps.repos.threads.list_turns(
        thread_id=thread_id, cursor=cursor, limit=limit
    )
    return ThreadResponse(
        thread_id=thread.thread_id,
        channel=thread.channel,
        frozen=thread.frozen,
        turns=[
            ThreadTurn(
                turn_id=t.turn_id,
                created_at=t.created_at,
                channel=t.channel,
                client_text=t.client_text,
                speech=t.speech,
                ui_payload=[UIComponent.model_validate(c) for c in t.ui_payload],
                evidence_id=t.evidence_id,
                service_type=t.service_type,
                intent=t.intent,
                error_code=t.error_code,
            )
            for t in turns
        ],
        next_cursor=next_cursor,
    )


@router.get(
    "/docs/sse-events",
    summary="JSON schema of the SSE event payloads",
    description="Documentation endpoint: the shapes of `token`, `ui`, `form_spec`, `citations`, `error`, `done`.",
)
async def sse_events_schema() -> dict[str, Any]:
    return SseEventCatalogue.model_json_schema()
