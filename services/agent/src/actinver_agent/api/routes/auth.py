"""``POST /v1/auth/step-up/challenge`` (ADR-0017 step 1).

Single-use, bound to the form and the declared amount, 120 s TTL. The device
signs the challenge with its biometric-gated hardware key; the signature comes
back as ``step_up_assertion`` on the form submission.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from actinver_agent.api.schemas import StepUpChallengeRequest, StepUpChallengeResponse
from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import (
    IdempotencyGuard,
    get_deps,
    idempotency_key,
    require_client,
)
from actinver_agent.auth.devkeys import amount_hash
from actinver_agent.deps import Dependencies
from actinver_agent.errors import api_error

router = APIRouter(prefix="/v1", tags=["auth"])


@router.post(
    "/auth/step-up/challenge",
    response_model=StepUpChallengeResponse,
    summary="Issue a single-use step-up challenge",
    description=(
        "Requires `Idempotency-Key`. The challenge is bound to `form_id` and the declared "
        "amount and expires in 120 s. Sign the raw challenge bytes with the device key "
        "(ES256, raw r||s) and send the base64url signature as `step_up_assertion`."
    ),
)
async def step_up_challenge(
    body: StepUpChallengeRequest,
    ctx: RequestContext = Depends(require_client),
    key: str = Depends(idempotency_key),
    deps: Dependencies = Depends(get_deps),
) -> StepUpChallengeResponse:
    if ctx.restricted:
        raise api_error("FORBIDDEN", detail="restricted device mode")
    guard = IdempotencyGuard(
        deps, key=key, client_id=ctx.client_id, payload=body.model_dump(mode="json")
    )
    if (replay := await guard.replay()) is not None:
        return StepUpChallengeResponse.model_validate(replay)
    stored = await deps.repos.form_specs.get(body.form_id)
    if stored is None or stored[0].client_id != ctx.client_id:
        raise api_error("NOT_FOUND", detail="form")
    challenge = await deps.transactions.issue_challenge(
        client_id=ctx.client_id,
        form_id=body.form_id,
        amount_hash=amount_hash(body.amount.amount, body.amount.currency),
    )
    response = StepUpChallengeResponse(
        challenge_id=challenge.challenge_id,
        challenge=challenge.challenge,
        expires_at=challenge.expires_at,
    )
    await guard.store(response.model_dump(mode="json"))
    return response
