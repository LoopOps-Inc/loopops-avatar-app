"""Runtime configuration. Every value is environment-driven; nothing is hardcoded.

Secrets are never carried by environment variables in dev/staging/prod. The
environment carries *references* (``secretsmanager://...``, ``kms://...``) that
``secrets.SecretResolver`` resolves at startup and holds in memory only. A
startup assertion fails the process if a configuration value *looks like* a
secret (docs/04-backend/01 §6, docs/05-security/04 §4).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class AuthSettings(BaseSettings):
    """Client authentication (docs/05-security/03 §1, ADR-0017)."""

    model_config = SettingsConfigDict(env_prefix="AUTH_")

    #: ``oidc`` validates RS256/ES256 tokens against the IdP JWKS.
    #: ``dev`` validates HS256 tokens signed with ``dev_signing_key_ref`` (local only).
    mode: Literal["oidc", "dev"] = "dev"
    issuer: str = "https://idp.local.actinver/"
    audience: str = "actinver-ai-advisor"
    jwks_url: str = ""
    dev_signing_key_ref: str = "env://AUTH_DEV_SIGNING_KEY"
    dev_password: SecretStr = SecretStr("actinver123")
    #: DPoP proof (RFC 9449). Required outside local; in local a bearer-only
    #: request is accepted so plain curls work, but a present proof is verified.
    dpop_required: bool = False
    dpop_clock_skew_s: int = 60
    dpop_nonce_ttl_s: int = 300
    access_token_max_ttl_s: int = 86400


class VertexSettings(BaseSettings):
    """Gemini via Vertex AI (ADR-0003)."""

    model_config = SettingsConfigDict(env_prefix="VERTEX_")

    project_id: str = ""
    location: str = "us-central1"
    model_fast: str = "gemini-2.5-flash"
    model_deep: str = "gemini-2.5-pro"
    temperature: float = 0.2
    top_p: float = 0.9
    seed: int = 7
    max_output_tokens_voice: int = 400
    max_output_tokens_chat: int = 800
    timeout_s: float = 20.0


class LlmSettings(BaseSettings):
    """Which model binding is active.

    ``vertex`` is the only production provider (ADR-0003). ``gemini_api`` (an
    AI Studio key) exists for local development only and is refused outside
    ``local``. ``stub`` is the deterministic templated fallback described in
    docs/01-architecture/01 §7 (model provider unavailable) and is what CI and
    the local stack use when no credentials are present.
    """

    model_config = SettingsConfigDict(env_prefix="LLM_")

    provider: Literal["vertex", "gemini_api", "stub"] = "stub"
    gemini_api_key_ref: str = ""


class LiveAvatarSettings(BaseSettings):
    """LiveAvatar LITE mode (ADR-0001, docs/01-architecture/05)."""

    model_config = SettingsConfigDict(env_prefix="LIVEAVATAR_")

    base_url: str = "https://api.liveavatar.com"
    api_key_ref: str = Field(
        default="secretsmanager://actinver/liveavatar/api-key",
        description="Secrets-manager reference, never the key itself",
    )
    avatar_id: str = "dd73ea75-1218-4ef3-92ce-606d5f7fbc0a"
    voice_id: str = ""
    is_sandbox: bool = True
    #: ``real`` talks to the vendor; ``stub`` emulates the vendor locally so the
    #: broker, framing and state machine can be exercised without credits.
    provider: Literal["real", "stub"] = "stub"
    max_session_duration_s: int = 1800
    keep_alive_interval_s: int = 240
    idle_prompt_s: int = 90
    idle_teardown_s: int = 150
    background_grace_s: int = 30
    max_concurrent_sessions: int = 100
    token_refresh_ratio: float = 0.8
    # Vendor audio contract - do not change without re-reading the API docs.
    audio_sample_rate_hz: int = 24_000
    audio_sample_width_bytes: int = 2
    audio_channels: int = 1
    audio_chunk_ms: int = 1000
    speak_started_timeout_s: float = 2.0


class VoiceSettings(BaseSettings):
    """Cascaded voice pipeline (ADR-0002)."""

    model_config = SettingsConfigDict(env_prefix="VOICE_")

    #: ``google`` uses Vertex/Google Cloud Speech + TTS; ``gemini_api`` uses the
    # AI Studio key for TTS and utterance-level STT (transcription on
    # ``utterance_end``); ``stub`` accepts dev-only text transcripts and
    # synthesises silence.
    provider: Literal["google", "gemini_api", "stub"] = "stub"
    stt_language: str = "es-MX"
    stt_model: str = "latest_long"
    stt_min_confidence: float = 0.60
    stt_sample_rate_hz: int = 16_000
    gemini_stt_model: str = "gemini-2.5-flash-lite"
    tts_voice_name: str = "es-MX-Neural2-A"
    gemini_tts_voice: str = "Puck"
    tts_speaking_rate: float = 1.0
    tts_sample_rate_hz: int = 24_000
    filler_threshold_ms: int = 400
    thinking_ceiling_s: float = 8.0
    stutter_restart_window_s: float = 1.5
    # Phrase hints materially improve Mexican financial-vocabulary recognition.
    stt_phrase_hints: tuple[str, ...] = (
        "Actinver",
        "CETES",
        "BIVA",
        "BMV",
        "TIIE",
        "UDI",
        "Banxico",
        "renta variable",
        "renta fija",
        "fondo de inversión",
        "casa de bolsa",
        "estado de cuenta",
        "rendimiento",
        "portafolio",
        "liquidez",
    )


class LimitsSettings(BaseSettings):
    """Budgets from docs/01-architecture/06 §3.4 and docs/04-backend/02 §2."""

    model_config = SettingsConfigDict(env_prefix="LIMITS_")

    max_tool_rounds: int = 4
    max_tool_calls_per_turn: int = 10
    tool_timeout_s: float = 3.0
    total_tool_budget_s: float = 8.0
    model_timeout_s: float = 20.0
    turn_hard_ceiling_s: float = 30.0
    max_rewrite_attempts: int = 2
    turns_per_minute: int = 20
    turns_per_day: int = 500
    avatar_minutes_per_day: int = 60
    max_message_chars: int = 2000
    form_ttl_s: int = 600
    step_up_challenge_ttl_s: int = 120
    idempotency_ttl_s: int = 86_400
    thread_history_page_size: int = 50


class ServiceEndpoints(BaseSettings):
    """Internal fail-closed dependencies (docs/04-backend/01 §2).

    Each may be ``inprocess`` (library mode, used by tests and single-binary
    dev runs) or an ``http(s)://`` base URL of the separately deployed service.
    """

    model_config = SettingsConfigDict(env_prefix="SVC_")

    suitability_url: str = "inprocess"
    guardrail_url: str = "inprocess"
    audit_url: str = "inprocess"
    transaction_url: str = "inprocess"
    request_timeout_s: float = 2.0
    health_timeout_s: float = 1.0


class ObjectStoreSettings(BaseSettings):
    """S3-compatible WORM tier (ADR-0011, ADR-0012). Locally: floci."""

    model_config = SettingsConfigDict(env_prefix="OBJECT_STORE_")

    endpoint: str = "http://localhost:4566"
    region: str = "us-east-1"
    bucket: str = "actinver-evidence-local"
    #: ``COMPLIANCE`` in production; ``GOVERNANCE`` in staging/local so records
    #: written in error are recoverable (ADR-0012 negative consequences).
    lock_mode: Literal["COMPLIANCE", "GOVERNANCE"] = "GOVERNANCE"
    access_key_ref: str = "env://AWS_ACCESS_KEY_ID"
    secret_key_ref: str = "env://AWS_SECRET_ACCESS_KEY"  # noqa: S105 - a reference, not a value
    retention_years: int = 5
    #: ``s3`` uses the SDK; ``memory`` is for unit tests only.
    provider: Literal["s3", "memory"] = "s3"


class SecretsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SECRETS_")

    #: AWS Secrets Manager endpoint (floci locally, the real service or an
    #: External-Secrets-synced file mount in Kubernetes).
    manager_endpoint: str = "http://localhost:4566"
    manager_region: str = "us-east-1"
    #: Mounted secret files for ``file://`` references (External Secrets Operator).
    file_root: str = "/var/run/secrets/actinver"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Environment = Environment.LOCAL
    service_name: str = "agent-orchestrator"
    service_role: Literal["agent", "suitability", "guardrail", "audit", "transaction"] = "agent"
    log_level: str = "INFO"
    host: str = "0.0.0.0"  # noqa: S104 - container binding, network policy scopes it
    port: int = 8443
    public_base_url: str = "http://localhost:8443"
    cors_origins: tuple[str, ...] = ("http://localhost:8080",)

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://postgres:local_only_not_a_secret@localhost:5432/actinver_agent"
    )
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    #: ``memory`` is for unit tests; production always uses ``redis``.
    cache_provider: Literal["redis", "memory"] = "redis"
    #: ``postgres`` for the LangGraph checkpointer; ``memory`` for unit tests.
    checkpointer_provider: Literal["postgres", "memory"] = "postgres"

    core_provider: Literal["synthetic", "http"] = "synthetic"
    core_api_base_url: str = "https://core.internal.actinver.local"
    core_api_mtls_cert_path: str = "/etc/certs/agent.crt"
    core_api_mtls_key_path: str = "/etc/certs/agent.key"
    core_api_ca_path: str = "/etc/certs/actinver-ca.pem"
    market_data_base_url: str = "https://marketdata.example.internal"
    market_data_api_key_ref: str = "secretsmanager://actinver/marketdata/api-key"
    crm_base_url: str = "https://crm.internal.actinver.local"
    oms_base_url: str = "https://oms.internal.actinver.local"
    news_search_base_url: str = "https://news-gateway.internal.actinver.local"
    research_base_url: str = "https://research.actinver.com"
    news_allowlist: tuple[str, ...] = (
        "eleconomista.com.mx",
        "elfinanciero.com.mx",
        "reuters.com",
    )

    otlp_endpoint: str = ""
    langfuse_host: str = ""
    client_hash_salt_ref: str = "env://CLIENT_HASH_SALT"

    form_spec_signing_key_ref: str = "kms://actinver/formspec-hmac"
    #: Held by suitability-service only. The agent role must NOT be able to
    #: resolve it; a startup assertion verifies that (docs/05-security/04 §2).
    suitability_signing_key_ref: str = "kms://actinver/suitability-hmac"

    prompt_version: str = "advisor-es-MX@2026-08-20"
    prompts_dir: str = "prompts"
    suitability_ruleset_version: int = 14
    service_guide_version: str = "2026-06"
    ai_disclosure_version: str = "2026-08"
    voice_recording_disclosure_version: str = "2026-08"

    auth: AuthSettings = Field(default_factory=AuthSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    vertex: VertexSettings = Field(default_factory=VertexSettings)
    avatar: LiveAvatarSettings = Field(default_factory=LiveAvatarSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    limits: LimitsSettings = Field(default_factory=LimitsSettings)
    services: ServiceEndpoints = Field(default_factory=ServiceEndpoints)
    object_store: ObjectStoreSettings = Field(default_factory=ObjectStoreSettings)
    secrets: SecretsSettings = Field(default_factory=SecretsSettings)

    @property
    def is_local(self) -> bool:
        return self.environment is Environment.LOCAL

    def validate_posture(self) -> None:
        """Refuse configurations the architecture forbids outside local."""
        if self.is_local:
            return
        problems: list[str] = []
        if self.llm.provider == "gemini_api":
            problems.append("LLM_PROVIDER=gemini_api is local-only (ADR-0003: Vertex AI)")
        if self.auth.mode == "dev":
            problems.append("AUTH_MODE=dev is local-only")
        if not self.auth.dpop_required:
            problems.append("AUTH_DPOP_REQUIRED must be true outside local (ADR-0017)")
        if self.cache_provider != "redis" or self.checkpointer_provider != "postgres":
            problems.append("memory cache/checkpointer are test-only")
        if self.environment is Environment.PROD and self.object_store.lock_mode != "COMPLIANCE":
            problems.append("OBJECT_STORE_LOCK_MODE must be COMPLIANCE in prod (ADR-0012)")
        if self.environment is Environment.PROD and self.core_provider == "synthetic":
            problems.append("CORE_PROVIDER=synthetic is not allowed in prod")
        if problems:
            raise RuntimeError("Invalid configuration posture: " + "; ".join(problems))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_posture()
    return settings
