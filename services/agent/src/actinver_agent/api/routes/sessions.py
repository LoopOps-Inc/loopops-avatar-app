"""``POST /v1/sessions`` - establish an app session (docs/04-backend/04 §2).

Returns the thread and what this client may do. ``capabilities`` is derived
from the client's contracts and the feature flags so enabling advisory for a
cohort is a server-side change with no app release.
"""

from __future__ import annotations

import hashlib
from typing import Any

import structlog
from fastapi import APIRouter, Depends

from actinver_agent.api.disclosure_docs import CONSENT_REQUIRED_FOR, current_version, public_id
from actinver_agent.api.schemas import (
    Capabilities,
    CreateSessionRequest,
    DisclosureRequired,
    ModeDefaults,
    PromotorContact,
    SessionClient,
    SessionResponse,
)
from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import get_deps, register_device_key, require_client
from actinver_agent.deps import Dependencies
from actinver_agent.graph.state import ConsentRecord, ConsentType, Entitlements

router = APIRouter(prefix="/v1", tags=["sessions"])
log = structlog.get_logger(__name__)

DEFAULT_PROMOTOR = PromotorContact(
    name="Tu asesor Actinver", phone="800 ACTINVER", hours="Lunes a viernes, 8:30 a 18:00"
)


def promotor_contact(context: dict[str, Any] | None) -> PromotorContact:
    promotor = (context or {}).get("promotor") or {}
    if not promotor:
        return DEFAULT_PROMOTOR
    return PromotorContact(
        name=str(promotor.get("name", DEFAULT_PROMOTOR.name)),
        phone=str(promotor.get("phone", DEFAULT_PROMOTOR.phone)),
        hours=str(promotor.get("hours", DEFAULT_PROMOTOR.hours)),
    )


def thread_id_for(client_id: str, channel: str, salt: str) -> str:
    """``threads.thread_id = sha256(client_id || channel || salt)`` (docs/01-architecture/04 §3.1)."""
    digest = hashlib.sha256(f"{client_id}|{channel}|{salt}".encode()).hexdigest()
    return f"th_{digest[:26]}"


def verify_attestation(token: str | None) -> bool | None:
    """Play Integrity / App Attest. A failure is a risk signal, not a block.

    Production verifies the token against the platform attestation service in an
    adapter; the development rule is: any non-empty token other than ``invalid``.
    """
    if token is None:
        return None
    return bool(token) and token.lower() != "invalid"


async def load_entitlements(
    deps: Dependencies, client_id: str
) -> tuple[Entitlements, dict[str, Any]]:
    context = await deps.core.get_client_context(client_id=client_id)
    raw = context.get("entitlements") or {}
    entitlements = Entitlements(
        contracted_for_advised_services=bool(raw.get("contracted_for_advised_services", False)),
        contracted_for_execution=bool(raw.get("contracted_for_execution", False)),
        permitted_product_families=list(raw.get("permitted_product_families", [])),
        daily_avatar_minutes_remaining=int(raw.get("daily_avatar_minutes_remaining", 0)),
    )
    return entitlements, context


async def disclosures_required(deps: Dependencies, client_id: str) -> list[DisclosureRequired]:
    records: list[ConsentRecord] = await deps.repos.consents.list_for_client(client_id)
    out: list[DisclosureRequired] = []
    for consent in ConsentType:
        version = current_version(deps.settings, consent)
        acknowledged = any(
            r.type is consent and r.granted and r.revoked_at is None and r.version == version
            for r in records
        )
        out.append(
            DisclosureRequired(
                id=public_id(consent),
                version=version,
                acknowledged=acknowledged,
                required_for=CONSENT_REQUIRED_FOR[consent],
                text_url=f"/v1/disclosures/{public_id(consent)}",
            )
        )
    return out


@router.post(
    "/sessions",
    response_model=SessionResponse,
    summary="Establish an app session",
    description=(
        "Creates or resumes the client's thread for the requested channel and returns the "
        "capabilities the app may render, the disclosures that still need acknowledgement, "
        "and mode defaults. Requires `Authorization: DPoP <token>` + `DPoP` proof "
        "(a plain Bearer token is accepted in local only)."
    ),
)
async def create_session(
    body: CreateSessionRequest,
    ctx: RequestContext = Depends(require_client),
    deps: Dependencies = Depends(get_deps),
) -> SessionResponse:
    entitlements, context = await load_entitlements(deps, ctx.client_id)
    if body.device_public_jwk is not None:
        await register_device_key(deps, ctx, body.device_public_jwk)
    attested = verify_attestation(body.attestation)
    restricted = ctx.restricted or attested is False
    if attested is False:
        log.warning("session.attestation_failed")

    salt = await deps.secrets.try_resolve(deps.settings.client_hash_salt_ref) or "local"
    thread = await deps.repos.threads.get_or_create(client_id=ctx.client_id, channel=body.channel)
    flags = deps.flags
    kill = await flags.kill_switch_active()
    voice_ok = await flags.is_on("advisor.voice_mode") and await flags.is_on("advisor.avatar")
    capabilities = Capabilities(
        chat=not kill and await flags.is_on("advisor.enabled"),
        voice=not kill and voice_ok,
        advisory=(
            not kill
            and entitlements.contracted_for_advised_services
            and await flags.is_on("advisor.intent.advisory_recommend")
        ),
        transactional=(
            not kill
            and not restricted
            and entitlements.contracted_for_execution
            and await flags.is_on("advisor.intent.transactional")
        ),
    )
    profile = context.get("investor_profile") or {}
    voice_settings = deps.settings.voice
    return SessionResponse(
        thread_id=thread.thread_id or thread_id_for(ctx.client_id, body.channel, salt),
        capabilities=capabilities,
        disclosures_required=await disclosures_required(deps, ctx.client_id),
        client=SessionClient(
            first_name=str(context.get("first_name", "")),
            risk_category=str(profile.get("risk_category", "")),
            profile_expires_at=str(profile["expires_at"]) if profile.get("expires_at") else None,
            register=context.get("register", "tu"),
        ),
        mode_defaults=ModeDefaults(
            default_mode="chat",
            voice_available=capabilities.voice,
            filler_threshold_ms=voice_settings.filler_threshold_ms,
            thinking_ceiling_s=voice_settings.thinking_ceiling_s,
            background_grace_s=deps.settings.avatar.background_grace_s,
        ),
        promotor=promotor_contact(context),
        kill_switch=kill,
        risk_mode="restricted" if restricted else "normal",
    )
