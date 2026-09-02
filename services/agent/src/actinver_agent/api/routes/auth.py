"""``POST /v1/auth/step-up/challenge`` (ADR-0017 step 1).

Single-use, bound to the form and the declared amount, 120 s TTL. The device
signs the challenge with its biometric-gated hardware key; the signature comes
back as ``step_up_assertion`` on the form submission.
"""

from __future__ import annotations

from hmac import compare_digest

from fastapi import APIRouter, Depends

from actinver_agent.api.schemas import (
    DevTokenRequest,
    DevTokenResponse,
    StepUpChallengeRequest,
    StepUpChallengeResponse,
)
from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import (
    IdempotencyGuard,
    get_deps,
    idempotency_key,
    require_client,
)
from actinver_agent.auth.devkeys import amount_hash, mint_dev_access_token
from actinver_agent.deps import Dependencies
from actinver_agent.errors import api_error

router = APIRouter(prefix="/v1", tags=["auth"])


@router.post(
    "/auth/dev-token",
    response_model=DevTokenResponse,
    summary="Mint a dev access token for testing and frontend investor switcher",
    description="Development-only token generator for frontend investor switching without CLI.",
)
async def mint_dev_token(
    body: DevTokenRequest,
    deps: Dependencies = Depends(get_deps),
) -> DevTokenResponse:
    if not compare_digest(
        body.password.get_secret_value(), deps.settings.auth.dev_password.get_secret_value()
    ):
        raise api_error("UNAUTHENTICATED")

    key: str | None = None
    if deps.settings.auth.dev_signing_key_ref:
        try:
            key = await deps.secrets.resolve(deps.settings.auth.dev_signing_key_ref)
        except Exception:
            pass
    if not key:
        import os

        key = os.environ.get("DEV_SIGNING_KEY", "test-dev-signing-key-32-bytes-long!")

    # The verifier rejects any token whose lifetime exceeds the configured
    # ceiling ("token_ttl_too_long"), so never mint one this service would
    # refuse: the ceiling is the upper bound, the request only shortens it.
    ttl_s = min(body.ttl_s, deps.settings.auth.access_token_max_ttl_s)

    token = mint_dev_access_token(
        key,
        body.client_id,
        roles=body.roles,
        ttl_s=ttl_s,
        issuer=deps.settings.auth.issuer,
        audience=deps.settings.auth.audience,
    )
    return DevTokenResponse(
        access_token=token,
        client_id=body.client_id,
        expires_in=ttl_s,
    )


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
