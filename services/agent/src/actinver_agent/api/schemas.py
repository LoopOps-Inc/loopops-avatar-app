"""Request/response models for the mobile/web-facing API (docs/04-backend/04).

The generated OpenAPI 3.1 document at ``/openapi.json`` is the source of truth;
these models are what it is generated from. Additive changes only in ``/v1``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from actinver_agent.graph.state import (
    ConsentType,
    FormSpec,
    Money,
    UIComponent,
)

# ── Sessions ───────────────────────────────────────────────────────────────────


class Capabilities(BaseModel):
    chat: bool
    voice: bool
    advisory: bool
    transactional: bool


class DisclosureRequired(BaseModel):
    id: str = Field(examples=["SERVICES_GUIDE"])
    version: str = Field(examples=["2026-06"])
    acknowledged: bool
    required_for: Literal["first_turn", "voice", "optional"]
    text_url: str | None = None


class SessionClient(BaseModel):
    first_name: str
    risk_category: str
    profile_expires_at: str | None = None
    register: Literal["tu", "usted"] = Field(default="tu")


class ModeDefaults(BaseModel):
    default_mode: Literal["chat", "voice"] = "chat"
    voice_available: bool = True
    filler_threshold_ms: int = 400
    thinking_ceiling_s: float = 8.0
    background_grace_s: int = 30


class PromotorContact(BaseModel):
    name: str
    phone: str
    hours: str


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal["chat", "voice"] = "chat"
    device_id: str | None = None
    #: Play Integrity / App Attest token. A failure is a risk signal, not a block.
    attestation: str | None = None
    locale: str = "es-MX"
    #: Device public key (EC P-256 JWK). Registered only when its RFC 7638 thumbprint
    #: equals the token's ``cnf.jkt`` (ADR-0017); a DPoP proof registers it implicitly.
    device_public_jwk: dict[str, Any] | None = None


class SessionResponse(BaseModel):
    thread_id: str
    thread_started_at: datetime
    capabilities: Capabilities
    disclosures_required: list[DisclosureRequired]
    client: SessionClient
    mode_defaults: ModeDefaults
    promotor: PromotorContact
    kill_switch: bool = False
    risk_mode: Literal["normal", "restricted"] = "normal"


# ── Messages / SSE ─────────────────────────────────────────────────────────────


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)
    locale: str = "es-MX"
    client_turn_id: str | None = Field(default=None, max_length=64)


class SseTokenEvent(BaseModel):
    text: str


class SseUiEvent(UIComponent):
    pass


class SseCitationsEvent(BaseModel):
    items: list[dict[str, Any]]


class SseErrorEvent(BaseModel):
    code: str
    message: str
    escalate: bool = False


class SseDoneEvent(BaseModel):
    turn_id: str
    evidence_id: str | None
    service_type: str
    service_subtype: str | None = None
    intent: str | None = None
    degraded_from: str | None = None
    disclosures_shown: dict[str, str] = Field(default_factory=dict)


class SseFormSpecEvent(FormSpec):
    pass


class SseEventCatalogue(BaseModel):
    """Documentation-only model listing the SSE event names and shapes."""

    token: SseTokenEvent
    ui: SseUiEvent
    form_spec: SseFormSpecEvent
    citations: SseCitationsEvent
    error: SseErrorEvent
    done: SseDoneEvent


# ── Thread history ─────────────────────────────────────────────────────────────


class ThreadTurn(BaseModel):
    turn_id: str
    created_at: datetime
    channel: str
    client_text: str
    speech: str | None
    ui_payload: list[UIComponent]
    evidence_id: str | None
    service_type: str
    intent: str
    error_code: str | None


class ThreadResponse(BaseModel):
    thread_id: str
    channel: str
    frozen: bool
    turns: list[ThreadTurn]
    next_cursor: str | None


# ── Forms and step-up ──────────────────────────────────────────────────────────


class StepUpChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    form_id: str
    amount: Money


class StepUpChallengeResponse(BaseModel):
    challenge_id: str
    challenge: str = Field(description="base64 nonce; sign it with the device key (ES256)")
    expires_at: datetime
    #: What the device must sign: base64url(sha256(challenge || form_id || amount_hash)).
    signing_input_hint: str = "ES256 (raw r||s, base64url) over the ASCII bytes of `challenge`"


class FormSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: dict[str, Any]
    acknowledgements: list[str] = Field(default_factory=list)
    challenge_id: str
    step_up_assertion: str = Field(description="base64url ES256 signature over the challenge")


class FormSubmitResponse(BaseModel):
    order_id: str
    status: str
    settlement_date: str
    evidence_id: str | None
    ui_payload: list[UIComponent] = Field(default_factory=list)
    speech: str | None = None


# ── Avatar ─────────────────────────────────────────────────────────────────────


class AvatarSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str
    orientation: Literal["landscape", "portrait"] = "portrait"


class AvatarSessionResponse(BaseModel):
    avatar_session_id: str
    livekit_url: str
    livekit_client_token: str
    max_session_duration_s: int
    expires_at: datetime
    audio_ws_path: str
    #: True when the vendor is emulated locally (LIVEAVATAR_PROVIDER=stub).
    emulated: bool = False


class AvatarStopRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    avatar_session_id: str
    reason: Literal["user", "background", "logout", "navigation", "error"] = "user"


class AvatarStopResponse(BaseModel):
    avatar_session_id: str
    stopped: bool
    duration_s: float
    speaking_s: float


class PreflightResponse(BaseModel):
    media_reachable: bool
    udp_available: bool | None = Field(
        default=None, description="Measured client-side; the server cannot know it"
    )
    estimated_rtt_ms: float | None
    voice_offered: bool
    reason: str | None = None


# ── Consents ───────────────────────────────────────────────────────────────────


class ConsentAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ConsentType
    version: str
    granted: bool = True
    channel: Literal["chat", "voice", "app"] = "app"


class ConsentView(BaseModel):
    type: ConsentType
    public_id: str
    current_version: str
    granted: bool
    granted_version: str | None
    granted_at: datetime | None
    revoked_at: datetime | None
    required_for: Literal["first_turn", "voice", "optional"]


class ConsentsResponse(BaseModel):
    consents: list[ConsentView]


class DisclosureText(BaseModel):
    id: str
    version: str
    text: str


# ── Config poll, telemetry, health ────────────────────────────────────────────


class DevTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str = Field(default="200001", description="Client ID or numero_cliente_unico")
    roles: list[str] = Field(default_factory=list, description="Roles to grant")
    ttl_s: int = Field(default=900, ge=60, le=86400, description="Token lifetime in seconds")


class DevTokenResponse(BaseModel):
    access_token: str
    client_id: str
    token_type: str = "Bearer"  # noqa: S105
    expires_in: int


class ClientConfigResponse(BaseModel):
    kill_switch: bool
    kill_switch_message: str | None
    voice_mode: bool
    avatar: bool
    advisory: bool
    transactional: bool
    disclosure_versions: dict[str, str]
    promotor: PromotorContact
    poll_interval_s: int = 30


class InvestorSummary(BaseModel):
    id_cliente_pk: int
    numero_cliente_unico: int
    nombre_completo: str
    rfc: str
    correo_electronico: str | None = None
    perfil_riesgo: str | None = None
    total_contratos: int = 4


class InvestorsListResponse(BaseModel):
    investors: list[InvestorSummary]
    total: int


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    at: datetime | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TelemetryBatch(BaseModel):
    events: list[TelemetryEvent] = Field(max_length=200)


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]


# ── Compliance console ─────────────────────────────────────────────────────────


class EvidenceListItem(BaseModel):
    evidence_id: str
    client_hash: str
    thread_id: str
    turn_id: str
    created_at: datetime
    service_type: str
    service_subtype: str
    intent: str
    product_ids: list[str]
    content_hash: str
    legal_hold: bool
    refused: bool


class EvidenceListResponse(BaseModel):
    items: list[EvidenceListItem]
    next_cursor: str | None


class ComplianceSummary(BaseModel):
    window: dict[str, datetime]
    turns_by_service_type: dict[str, int]
    suitability_outcomes: dict[str, int]
    guardrail_blocks_by_reason: dict[str, int]
    escalations: int
    degradations: int
    refusals: int
    evidence_records: int
    model_versions: dict[str, int]
    prompt_versions: dict[str, int]


class FlagView(BaseModel):
    name: str
    value: str
    default: str
    owner: str
    expires_at: str


class FlagUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    reason: str = Field(min_length=3, max_length=500)


class RevokeSessionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_ids: list[str] = Field(default_factory=list, max_length=1000)
    issued_before: datetime | None = None
    reason: str = Field(min_length=3, max_length=500)


class ArcoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    kind: Literal["acceso", "rectificacion", "cancelacion", "oposicion", "portabilidad"]
    reason: str = Field(min_length=3, max_length=1000)


class ArcoResponse(BaseModel):
    request_id: str
    kind: str
    opened_at: datetime
    export_url: str | None = None
    export_expires_at: datetime | None = None
    retained_data_statement_es: str | None = None
    retained_categories: list[dict[str, str]] = Field(default_factory=list)


class ChainVerifyResponse(BaseModel):
    thread_id: str
    ok: bool
    records: int
    first_divergent_evidence_id: str | None
