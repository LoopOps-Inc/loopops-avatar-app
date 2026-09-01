"""Ports: the interfaces between the graph/API and every pluggable dependency.

Hexagonal boundary. Domain and graph code depend only on these Protocols.
Adapters (``adapters/``, ``clients/``, the ``*_client``/``*_service`` modules)
implement them. Provider SDKs are imported under ``adapters/`` only (ADR-0011).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from actinver_agent.graph.state import (
    AdvisorState,
    ConsentRecord,
    ConsentType,
    Entitlements,
    FormSpec,
    GuardrailVerdict,
    Intent,
    InvestorProfile,
    ProductProfile,
    SuitabilityReport,
)

# ── Model bindings ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    intent: Intent
    confidence: float
    runner_up: Intent | None = None
    #: ``product_discover`` framed against this client's profile → asesorado.
    profile_filtered: bool = False
    model: str = "rules"
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True, slots=True)
class GenerationResult:
    speech: str
    #: Product ids the model proposes; only ``suitability_gate`` may approve them.
    candidate_product_ids: list[str] = field(default_factory=list)
    proposed_amount: Decimal | None = None
    model: str = "stub"
    provider: str = "stub"
    input_tokens: int = 0
    output_tokens: int = 0
    ttft_ms: int = 0
    safety_blocked: bool = False


class IntentClassifier(Protocol):
    async def classify(
        self, *, text: str, history: list[str], locale: str
    ) -> ClassificationResult: ...


class Planner(Protocol):
    async def plan(
        self, *, state: AdvisorState, declarations: list[dict[str, Any]]
    ) -> list[ToolCall]: ...


class Generator(Protocol):
    async def generate(
        self,
        *,
        state: AdvisorState,
        system_prompt: str,
        model: str,
        max_tokens: int,
        rewrite_hint: str | None,
    ) -> GenerationResult: ...


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


# ── Fail-closed internal controls ─────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class EvaluationInput:
    """Everything the suitability engine may look at, and nothing more."""

    today: datetime
    amount: Decimal
    portfolio_total: Decimal
    current_weight_by_product: dict[str, float]
    current_weight_by_asset_class: dict[str, float]
    liquid_pct: float
    diversification_limits: dict[str, float]


class SuitabilityPort(Protocol):
    async def evaluate(
        self,
        *,
        client_id: str,
        profile: InvestorProfile,
        products: list[ProductProfile],
        ctx: EvaluationInput,
    ) -> SuitabilityReport: ...

    async def verify(self, *, report: SuitabilityReport) -> bool: ...

    async def health(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class OutputCheckRequest:
    speech: str
    intent: Intent | None
    locale: str
    register: str
    provenance_keys: frozenset[str]
    stripped_product_terms: tuple[str, ...]
    rewrite_attempts: int
    max_rewrite_attempts: int
    #: Sentence-level checks (voice) skip disclosure injection.
    sentence_mode: bool = False


class GuardrailPort(Protocol):
    async def check_input(
        self, *, text: str, transcript_confidence: float | None
    ) -> tuple[GuardrailVerdict, str]:
        """Returns (verdict, redacted_text)."""
        ...

    async def scan_retrieved(self, *, text: str) -> bool:
        """True when retrieved third-party content carries an injection attempt."""
        ...

    async def check_output(self, request: OutputCheckRequest) -> GuardrailVerdict: ...

    async def disclosure_texts(self, ids: list[str]) -> dict[str, tuple[str, str]]:
        """id → (text, version). Verbatim, legal-approved."""
        ...

    async def health(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class EvidenceWriteResult:
    evidence_id: str
    content_hash: str | None
    spooled: bool


class AuditPort(Protocol):
    async def write(self, *, record: dict[str, Any], fail_closed: bool) -> EvidenceWriteResult: ...

    async def health(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class StepUpChallenge:
    challenge_id: str
    challenge: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class OrderReceipt:
    order_id: str
    status: str
    settlement_date: str
    evidence_id: str | None
    idempotent_replay: bool = False


class TransactionPort(Protocol):
    async def issue_challenge(
        self, *, client_id: str, form_id: str, amount_hash: str
    ) -> StepUpChallenge: ...

    async def execute(
        self,
        *,
        client_id: str,
        form_spec: FormSpec,
        values: dict[str, Any],
        acknowledgements: list[str],
        step_up_assertion: str,
        challenge_id: str,
        idempotency_key: str,
        suitability_verdict_id: str | None,
        jkt: str | None = None,
        device_id: str | None = None,
    ) -> OrderReceipt: ...

    async def health(self) -> bool: ...


# ── Core systems (through tool-gateway) ───────────────────────────────────────


class CoreBankingPort(Protocol):
    """mTLS client for Actinver core. Read-only. ``client_id`` is always injected."""

    async def get_client_context(self, *, client_id: str) -> dict[str, Any]:
        """first_name, entitlements, register, promotor contact."""
        ...

    async def get_investor_profile(self, *, client_id: str) -> dict[str, Any]: ...
    async def get_positions(self, *, client_id: str) -> dict[str, Any]: ...
    async def get_performance(self, *, client_id: str, period: str) -> dict[str, Any]: ...
    async def get_attribution(
        self, *, client_id: str, period: str, granularity: str
    ) -> dict[str, Any]: ...
    async def get_cash_balance(self, *, client_id: str) -> dict[str, Any]: ...
    async def get_accounts(self, *, client_id: str) -> dict[str, Any]: ...
    async def get_transaction_history(self, *, client_id: str, **kw: Any) -> dict[str, Any]: ...
    async def get_statement(self, *, client_id: str, year: int, month: int) -> dict[str, Any]: ...
    async def search_products(self, **filters: Any) -> dict[str, Any]: ...
    async def get_product_detail(self, *, product_id: str) -> dict[str, Any]: ...
    async def get_product_profile(self, *, product_id: str) -> dict[str, Any]: ...
    async def compare_products(self, *, product_ids: list[str]) -> dict[str, Any]: ...
    async def get_diversification_limits(self) -> dict[str, float]: ...
    async def get_transaction_requirements(
        self, *, client_id: str, **kw: Any
    ) -> dict[str, Any]: ...
    async def simulate_investment(self, **kw: Any) -> dict[str, Any]: ...
    async def calculate_fees_and_taxes(self, *, client_id: str, **kw: Any) -> dict[str, Any]: ...
    async def get_device_public_key(self, *, client_id: str, device_id: str) -> str | None: ...
    async def health(self) -> bool: ...


class MarketDataPort(Protocol):
    async def get_quotes(self, *, symbols: list[str]) -> dict[str, Any]: ...
    async def get_calendar(self, **kw: Any) -> dict[str, Any]: ...
    async def health(self) -> bool: ...


class NewsPort(Protocol):
    async def search(self, **kw: Any) -> dict[str, Any]: ...
    async def search_research(self, **kw: Any) -> dict[str, Any]: ...
    async def health(self) -> bool: ...


class CrmPort(Protocol):
    async def create_escalation(self, *, client_id: str, **kw: Any) -> dict[str, Any]: ...
    async def file_complaint(self, *, client_id: str, **kw: Any) -> dict[str, Any]: ...
    async def get_services_guide(self, *, section: str) -> dict[str, Any]: ...
    async def health(self) -> bool: ...


class OmsPort(Protocol):
    async def place_order(
        self, *, client_id: str, order: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]: ...

    async def health(self) -> bool: ...


# ── Infrastructure ─────────────────────────────────────────────────────────────


class CachePort(Protocol):
    async def get(self, key: str) -> bytes | None: ...
    async def set(self, key: str, value: bytes, *, ttl_s: int | None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def incr(self, key: str, *, ttl_s: int | None = None) -> int: ...
    async def sliding_window_hit(self, key: str, *, limit: int, window_s: int) -> bool:
        """Record a hit; True when within the limit."""
        ...

    async def acquire_slot(self, key: str, *, limit: int, member: str, ttl_s: int) -> bool: ...
    async def release_slot(self, key: str, *, member: str) -> None: ...
    async def slot_count(self, key: str) -> int: ...
    async def get_flag(self, name: str) -> str | None: ...
    async def set_flag(self, name: str, value: str) -> None: ...
    async def health(self) -> bool: ...


class ObjectStorePort(Protocol):
    async def put_immutable(
        self, key: str, body: bytes, *, retain_until: datetime, content_type: str
    ) -> None: ...

    async def put_expiring(
        self, key: str, body: bytes, *, expires_at: datetime, content_type: str
    ) -> None: ...

    async def get(self, key: str) -> bytes | None: ...
    async def list_keys(self, prefix: str) -> list[str]: ...
    async def set_legal_hold(self, key: str, *, on: bool) -> None: ...
    async def presign_get(self, key: str, *, ttl_s: int) -> str: ...
    async def health(self) -> bool: ...


class ChainStorePort(Protocol):
    async def head_hash(self, thread_id: str) -> str | None: ...
    async def set_head(self, thread_id: str, content_hash: str, evidence_id: str) -> None: ...
    async def all_heads(self) -> dict[str, str]: ...


class SpoolPort(Protocol):
    async def enqueue(self, record: dict[str, Any]) -> None: ...
    async def dequeue(self, limit: int) -> list[tuple[int, dict[str, Any]]]: ...
    async def ack(self, ids: list[int]) -> None: ...
    async def depth(self) -> int: ...


class SecretsBackendPort(Protocol):
    async def get(self, name: str) -> str: ...


# ── Voice and avatar ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Transcript:
    text: str
    is_final: bool
    confidence: float
    language: str


class SpeechToTextPort(Protocol):
    def stream(self, audio_frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]: ...


class TextToSpeechPort(Protocol):
    def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Yields raw PCM s16le mono @ 24 kHz."""
        ...


@dataclass(slots=True)
class VendorSession:
    session_id: str
    session_token: str = field(repr=False)
    livekit_url: str = ""
    livekit_client_token: str = field(default="", repr=False)
    #: Never forwarded to any client - permits publishing into the room.
    livekit_agent_token: str = field(default="", repr=False)
    ws_url: str = field(default="", repr=False)
    max_session_duration_s: int = 1800

    def client_payload(self) -> dict[str, Any]:
        """Exactly what the app is allowed to receive (docs/04-backend/04 §2)."""
        return {
            "avatar_session_id": self.session_id,
            "livekit_url": self.livekit_url,
            "livekit_client_token": self.livekit_client_token,
            "max_session_duration_s": self.max_session_duration_s,
        }


class AvatarControlPort(Protocol):
    """The vendor WebSocket. Owns audio framing and the avatar state machine."""

    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def speak(self, pcm: bytes, *, flush: bool = False) -> str: ...
    async def speak_end(self, event_id: str) -> None: ...
    async def interrupt(self) -> None: ...
    async def start_listening(self) -> None: ...
    async def stop_listening(self) -> None: ...
    async def keep_alive(self) -> None: ...
    @property
    def connected(self) -> bool: ...
    @property
    def speaking_seconds(self) -> float: ...
    @property
    def first_frame_ms(self) -> float | None: ...


class AvatarVendorPort(Protocol):
    async def create_session(self) -> VendorSession: ...
    async def stop_session(self, session: VendorSession) -> None: ...
    async def keep_alive(self, session: VendorSession) -> None: ...
    def control_channel(self, session: VendorSession) -> AvatarControlPort: ...
    async def preflight(self) -> tuple[bool, float | None]:
        """(reachable, rtt_ms) against the vendor API."""
        ...


# ── Repositories ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ThreadRecord:
    thread_id: str
    client_id: str
    channel: str
    created_at: datetime
    frozen: bool
    turn_count: int


@dataclass(frozen=True, slots=True)
class TurnRecord:
    turn_id: str
    thread_id: str
    created_at: datetime
    channel: str
    client_text: str
    speech: str | None
    ui_payload: list[dict[str, Any]]
    evidence_id: str | None
    service_type: str
    intent: str
    error_code: str | None


class ThreadRepository(Protocol):
    async def get_or_create(self, *, client_id: str, channel: str) -> ThreadRecord: ...
    async def get(self, thread_id: str) -> ThreadRecord | None: ...
    async def append_turn(self, turn: TurnRecord) -> None: ...
    async def list_turns(
        self, *, thread_id: str, cursor: str | None, limit: int
    ) -> tuple[list[TurnRecord], str | None]: ...

    async def set_frozen(self, thread_id: str, *, frozen: bool) -> None: ...
    async def list_for_client(self, client_id: str) -> list[ThreadRecord]: ...


class ConsentRepository(Protocol):
    async def list_for_client(self, client_id: str) -> list[ConsentRecord]: ...
    async def record(self, consent: ConsentRecord) -> None: ...
    async def revoke(self, *, client_id: str, type: ConsentType, at: datetime) -> bool: ...
    async def has_active(
        self, *, client_id: str, type: ConsentType, version: str | None
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class DeviceBinding:
    client_id: str
    device_id: str
    jkt: str
    public_key_jwk: dict[str, Any]
    registered_at: datetime
    attestation_verified: bool


class DeviceRepository(Protocol):
    async def get(self, *, client_id: str, jkt: str) -> DeviceBinding | None: ...
    async def register(self, binding: DeviceBinding) -> None: ...


class FormSpecRepository(Protocol):
    async def store(self, spec: FormSpec, *, status: str) -> None: ...
    async def get(self, form_id: str) -> tuple[FormSpec, str] | None: ...
    async def mark(self, form_id: str, *, status: str) -> None: ...
    async def record_submission(
        self,
        *,
        form_id: str,
        client_id: str,
        values: dict[str, Any],
        acknowledgements: list[str],
        disclosure_versions: dict[str, str],
        step_up_challenge_id: str,
        order_id: str | None,
        idempotency_key: str,
    ) -> None: ...


class IdempotencyRepository(Protocol):
    async def get(self, key: str) -> tuple[str, dict[str, Any]] | None:
        """Returns (request_hash, stored_response) if the key was used."""
        ...

    async def put(
        self, key: str, *, request_hash: str, response: dict[str, Any], ttl_s: int
    ) -> None: ...


class ChallengeRepository(Protocol):
    async def store(
        self,
        *,
        challenge_id: str,
        client_id: str,
        form_id: str,
        amount_hash: str,
        nonce: str,
        expires_at: datetime,
    ) -> None: ...

    async def consume(self, *, challenge_id: str, client_id: str) -> dict[str, Any] | None:
        """Single-use: returns the challenge row and marks it used, or None."""
        ...


@dataclass(frozen=True, slots=True)
class AvatarSessionRecord:
    avatar_session_id: str
    client_id: str
    thread_id: str
    vendor_session_id: str
    started_at: datetime
    ended_at: datetime | None
    duration_s: float
    speaking_s: float
    end_reason: str | None


class AvatarSessionRepository(Protocol):
    async def create(self, record: AvatarSessionRecord) -> None: ...
    async def finish(
        self,
        avatar_session_id: str,
        *,
        ended_at: datetime,
        duration_s: float,
        speaking_s: float,
        end_reason: str,
    ) -> None: ...

    async def minutes_used_today(self, client_id: str) -> float: ...
    async def get(self, avatar_session_id: str) -> AvatarSessionRecord | None: ...


@dataclass(frozen=True, slots=True)
class EvidenceIndexRow:
    evidence_id: str
    client_id: str
    thread_id: str
    turn_id: str
    created_at: datetime
    service_type: str
    service_subtype: str
    intent: str
    product_ids: list[str]
    object_key: str
    content_hash: str
    legal_hold: bool
    refused: bool


class EvidenceIndexRepository(Protocol):
    async def index(self, row: EvidenceIndexRow) -> None: ...
    async def query(
        self,
        *,
        client_id: str | None,
        thread_id: str | None,
        since: datetime | None,
        until: datetime | None,
        service_type: str | None,
        product_id: str | None,
        refused: bool | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[EvidenceIndexRow], str | None]: ...

    async def get(self, evidence_id: str) -> EvidenceIndexRow | None: ...
    async def set_legal_hold(self, *, thread_id: str, on: bool) -> int: ...
    async def counts(self, *, since: datetime, until: datetime) -> dict[str, Any]: ...


class AccessLogRepository(Protocol):
    """Separate audit trail for reads of evidence (control EV-05)."""

    async def log(self, *, actor: str, action: str, scope: dict[str, Any], reason: str) -> None: ...


class ArcoRepository(Protocol):
    async def open_request(
        self, *, request_id: str, client_id: str, kind: str, opened_at: datetime
    ) -> None: ...

    async def close_request(
        self, *, request_id: str, closed_at: datetime, export_key: str | None
    ) -> None: ...

    async def list_requests(self, *, client_id: str | None) -> list[dict[str, Any]]: ...


class RulesetRepository(Protocol):
    async def record_version(
        self, *, version: int, rules: list[dict[str, Any]], published_at: datetime
    ) -> None: ...

    async def list_versions(self) -> list[int]: ...


class AudioSegmentRepository(Protocol):
    async def record(
        self,
        *,
        thread_id: str,
        turn_id: str,
        segment_id: str,
        object_key: str,
        speaker: str,
        consent_version: str,
        created_at: datetime,
    ) -> None: ...

    async def count_without_consent(self) -> int: ...


# ── Misc callables ─────────────────────────────────────────────────────────────

EntitlementsLoader = Callable[[str], Awaitable[tuple[Entitlements, dict[str, Any]]]]
