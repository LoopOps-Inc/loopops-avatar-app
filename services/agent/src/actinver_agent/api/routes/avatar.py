"""Avatar session lifecycle and the audio WebSocket (docs/04-backend/04 §2).

The response to ``POST /v1/avatar/session`` contains only what the app is
allowed to have. ``X-API-KEY``, the vendor session token and
``livekit_agent_token`` never appear here - asserted by
``tests/api/test_avatar.py`` and by the CI grep on the client bundle.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, WebSocket

from actinver_agent.api.disclosure_docs import current_version
from actinver_agent.api.routes.threads import owned_thread
from actinver_agent.api.schemas import (
    AvatarSessionRequest,
    AvatarSessionResponse,
    AvatarStopRequest,
    AvatarStopResponse,
    PreflightResponse,
)
from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import (
    IdempotencyGuard,
    get_deps,
    idempotency_key,
    require_client,
)
from actinver_agent.avatar.broker import AvatarBroker
from actinver_agent.deps import Dependencies, get_current
from actinver_agent.errors import api_error
from actinver_agent.graph.state import ConsentType
from actinver_agent.voice.ws_handler import AudioSocketHandler

router = APIRouter(prefix="/v1", tags=["avatar"])
log = structlog.get_logger(__name__)


def _broker(deps: Dependencies) -> AvatarBroker:
    if deps.broker is None:
        raise api_error("VOICE_UNAVAILABLE", detail="broker not configured")
    return deps.broker


@router.get(
    "/avatar/preflight",
    response_model=PreflightResponse,
    summary="Media-path reachability check before billing starts",
    description=(
        "Call before offering voice mode. `udp_available` is measured client-side and is "
        "therefore null here; `media_reachable` and `estimated_rtt_ms` are measured from the "
        "broker to the vendor. `voice_offered` folds in flags, capacity and vendor reachability."
    ),
)
async def preflight(
    ctx: RequestContext = Depends(require_client),
    deps: Dependencies = Depends(get_deps),
) -> PreflightResponse:
    result = await _broker(deps).preflight()
    return PreflightResponse(udp_available=None, **result)


@router.post(
    "/avatar/session",
    response_model=AvatarSessionResponse,
    summary="Start an avatar session (LITE mode)",
    description=(
        "Requires `Idempotency-Key` and the `VOICE_RECORDING` consent at its current version. "
        "Returns the LiveKit URL and a room-scoped client token only. Errors: "
        "`VOICE_CONSENT_REQUIRED` 403, `VOICE_UNAVAILABLE` 503, `AVATAR_CAPACITY` 503, "
        "`AVATAR_BUDGET_EXHAUSTED` 429, `KILL_SWITCH` 503."
    ),
)
async def start_session(
    body: AvatarSessionRequest,
    ctx: RequestContext = Depends(require_client),
    key: str = Depends(idempotency_key),
    deps: Dependencies = Depends(get_deps),
) -> AvatarSessionResponse:
    guard = IdempotencyGuard(
        deps, key=key, client_id=ctx.client_id, payload=body.model_dump(mode="json")
    )
    if (replay := await guard.replay()) is not None:
        return AvatarSessionResponse.model_validate(replay)
    await owned_thread(deps, ctx, body.thread_id)

    consent_version = current_version(deps.settings, ConsentType.VOICE_RECORDING)
    if not await deps.repos.consents.has_active(
        client_id=ctx.client_id, type=ConsentType.VOICE_RECORDING, version=consent_version
    ):
        raise api_error("VOICE_CONSENT_REQUIRED")

    context = await deps.core.get_client_context(client_id=ctx.client_id)
    session = await _broker(deps).start(
        ctx,
        thread_id=body.thread_id,
        first_name=str(context.get("first_name", "")),
        consent_version=consent_version,
        orientation=body.orientation,
    )
    payload = session.vendor.client_payload()
    response = AvatarSessionResponse(
        avatar_session_id=session.avatar_session_id,
        livekit_url=payload["livekit_url"],
        livekit_client_token=payload["livekit_client_token"],
        max_session_duration_s=int((session.expires_at - session.started_at).total_seconds()),
        expires_at=session.expires_at,
        audio_ws_path=f"/v1/avatar/{session.avatar_session_id}/audio",
        emulated=deps.settings.avatar.provider == "stub",
    )
    await guard.store(response.model_dump(mode="json"))
    return response


@router.post(
    "/avatar/session/stop",
    response_model=AvatarStopResponse,
    summary="Stop an avatar session",
    description="Idempotent. `reason=background` applies the 30 s grace before teardown.",
)
async def stop_session(
    body: AvatarStopRequest,
    ctx: RequestContext = Depends(require_client),
    key: str = Depends(idempotency_key),
    deps: Dependencies = Depends(get_deps),
) -> AvatarStopResponse:
    guard = IdempotencyGuard(
        deps, key=key, client_id=ctx.client_id, payload=body.model_dump(mode="json")
    )
    if (replay := await guard.replay()) is not None:
        return AvatarStopResponse.model_validate(replay)
    broker = _broker(deps)
    session = broker.get(body.avatar_session_id)
    if session is None:
        record = await deps.repos.avatar_sessions.get(body.avatar_session_id)
        if record is None or record.client_id != ctx.client_id:
            raise api_error("NOT_FOUND", detail="avatar_session")
        response = AvatarStopResponse(
            avatar_session_id=body.avatar_session_id,
            stopped=True,
            duration_s=record.duration_s,
            speaking_s=record.speaking_s,
        )
        await guard.store(response.model_dump(mode="json"))
        return response
    if session.client_id != ctx.client_id:
        raise api_error("NOT_FOUND", detail="avatar_session")
    if body.reason == "background":
        broker.background_grace(body.avatar_session_id)
        response = AvatarStopResponse(
            avatar_session_id=body.avatar_session_id,
            stopped=False,
            duration_s=session.elapsed_s,
            speaking_s=session.speaking_seconds,
        )
    else:
        stopped = await broker.stop(body.avatar_session_id, reason=body.reason)
        assert stopped is not None
        response = AvatarStopResponse(
            avatar_session_id=body.avatar_session_id,
            stopped=True,
            duration_s=stopped.elapsed_s,
            speaking_s=stopped.speaking_seconds,
        )
    await guard.store(response.model_dump(mode="json"))
    return response


@router.websocket("/avatar/{avatar_session_id}/audio")
async def audio_socket(websocket: WebSocket, avatar_session_id: str) -> None:
    """Bidirectional audio path. See ``voice.ws_handler`` for the message catalogue.

    Authenticate with `?access_token=` or a first `{"type":"auth","token":"..."}` message.
    """
    deps = get_current()
    if deps.broker is None:
        await websocket.close(code=1013)
        return
    handler = AudioSocketHandler(deps, deps.broker)
    await handler.handle(websocket, avatar_session_id)


def _utc_now() -> datetime:
    return datetime.now(UTC)
