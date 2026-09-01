"""``GET /v1/config`` - the remote-config poll the app uses for the kill switch
(ADR-0015 §kill switch semantics, ADR-0007). Unauthenticated, rate limited."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from actinver_agent.api.disclosure_docs import current_version, public_id
from actinver_agent.api.routes.sessions import promotor_contact
from actinver_agent.api.schemas import ClientConfigResponse
from actinver_agent.auth.dependencies import get_deps
from actinver_agent.auth.ratelimit import RateLimiter
from actinver_agent.deps import Dependencies
from actinver_agent.errors import api_error
from actinver_agent.flags import KILL_SWITCH_MESSAGE_ES
from actinver_agent.graph.state import ConsentType

router = APIRouter(prefix="/v1", tags=["config"])


@router.get(
    "/config",
    response_model=ClientConfigResponse,
    summary="Client configuration and kill-switch poll",
    description=(
        "Polled by the app every ``poll_interval_s``. When ``kill_switch`` is true the app "
        "hides the chat and voice entry points and shows ``kill_switch_message``. "
        "Flag state propagates in under 30 s without a deploy."
    ),
)
async def client_config(
    request: Request, deps: Dependencies = Depends(get_deps)
) -> ClientConfigResponse:
    client_host = request.client.host if request.client else "unknown"
    decision = await RateLimiter(deps.settings, deps.cache).check_generic(
        key=f"config:{client_host}", limit=120, window_s=60
    )
    if not decision.allowed:
        raise api_error("RATE_LIMITED", retry_after_s=decision.retry_after_s)
    flags = deps.flags
    kill = await flags.kill_switch_active()
    return ClientConfigResponse(
        kill_switch=kill,
        kill_switch_message=KILL_SWITCH_MESSAGE_ES if kill else None,
        voice_mode=await flags.is_on("advisor.voice_mode") and not kill,
        avatar=await flags.is_on("advisor.avatar") and not kill,
        advisory=await flags.is_on("advisor.intent.advisory_recommend") and not kill,
        transactional=await flags.is_on("advisor.intent.transactional") and not kill,
        disclosure_versions={public_id(c): current_version(deps.settings, c) for c in ConsentType},
        promotor=promotor_contact(None),
    )
