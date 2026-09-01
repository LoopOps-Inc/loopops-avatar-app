"""Graph state and the domain types that flow through it.

Two invariants are asserted at node boundaries (docs/01-architecture/06 §2.1):

1. ``client_id`` is written exactly once, at graph entry, from the validated
   request context. No node may change it. This is the control that prevents a
   prompt injection from causing cross-client data access (ADR-0014).
2. Every scalar that appears in ``ui_payload`` has a matching entry in
   ``provenance``. The composer refuses to emit otherwise.

Everything a regulator may ask about - profiles (DCGSI Anexo 3 y 4), verdicts
(Art. 5), disclosures, consents (Art. 26 / LFPDPPP) - is typed here so the
evidence record is assembled from typed objects, never from loose dicts.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── Intents ────────────────────────────────────────────────────────────────────


class Intent(StrEnum):
    PORTFOLIO_INSPECT = "portfolio_inspect"
    PORTFOLIO_EXPLAIN = "portfolio_explain"
    MARKET_CONTEXT = "market_context"
    PRODUCT_DISCOVER = "product_discover"
    ADVISORY_RECOMMEND = "advisory_recommend"
    SIMULATE = "simulate"
    TRANSACT_BUY = "transact_buy"
    TRANSACT_SELL = "transact_sell"
    TRANSACT_SWITCH = "transact_switch"
    TRANSACT_REDEEM = "transact_redeem"
    PROFILE_UPDATE = "profile_update"
    ACCOUNT_ADMIN = "account_admin"
    ESCALATE = "escalate"
    COMPLAINT = "complaint"
    OUT_OF_SCOPE = "out_of_scope"


ADVISORY_INTENTS: frozenset[Intent] = frozenset({Intent.ADVISORY_RECOMMEND, Intent.SIMULATE})
TRANSACTIONAL_INTENTS: frozenset[Intent] = frozenset(
    {Intent.TRANSACT_BUY, Intent.TRANSACT_SELL, Intent.TRANSACT_SWITCH, Intent.TRANSACT_REDEEM}
)
DEEP_MODEL_INTENTS: frozenset[Intent] = (
    ADVISORY_INTENTS | TRANSACTIONAL_INTENTS | {Intent.PORTFOLIO_EXPLAIN, Intent.MARKET_CONTEXT}
)
#: Intents answered without a model call at all (docs/01-architecture/06 §3.1).
NO_MODEL_INTENTS: frozenset[Intent] = frozenset(
    {Intent.OUT_OF_SCOPE, Intent.ESCALATE, Intent.COMPLAINT}
)

ServiceType = Literal["asesorado", "no_asesorado"]

#: DCGSI classification per intent (docs/06-compliance/02 §1). ``product_discover``
#: and ``simulate`` are refined at runtime (profile-filtered → asesorado).
SERVICE_SUBTYPE: dict[Intent, str] = {
    Intent.PORTFOLIO_INSPECT: "informacion",
    Intent.PORTFOLIO_EXPLAIN: "informacion",
    Intent.MARKET_CONTEXT: "informacion",
    Intent.PRODUCT_DISCOVER: "comercializacion_o_promocion",
    Intent.ADVISORY_RECOMMEND: "asesoria_de_inversiones",
    Intent.SIMULATE: "informacion",
    Intent.TRANSACT_BUY: "ejecucion_de_operaciones",
    Intent.TRANSACT_SELL: "ejecucion_de_operaciones",
    Intent.TRANSACT_SWITCH: "ejecucion_de_operaciones",
    Intent.TRANSACT_REDEEM: "ejecucion_de_operaciones",
    Intent.PROFILE_UPDATE: "administrativo",
    Intent.ACCOUNT_ADMIN: "administrativo",
    Intent.ESCALATE: "administrativo",
    Intent.COMPLAINT: "condusef_une",
    Intent.OUT_OF_SCOPE: "fuera_de_alcance",
}


# ── Money ──────────────────────────────────────────────────────────────────────


class Money(BaseModel):
    """Always ``{amount: decimal string, currency}`` - never a bare number
    (docs/04-backend/04 §1). A value without a currency is rejected, not
    defaulted to MXN (docs/07-data-governance/03 §6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: str
    currency: Literal["MXN", "USD", "EUR"]

    @field_validator("amount")
    @classmethod
    def _decimal_string(cls, value: str) -> str:
        try:
            parsed = Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise ValueError("amount must be a decimal string") from exc
        if not parsed.is_finite():
            raise ValueError("amount must be finite")
        return format(parsed, "f")

    @property
    def decimal(self) -> Decimal:
        return Decimal(self.amount)

    @classmethod
    def of(cls, amount: Decimal | int | str, currency: str = "MXN") -> Money:
        return cls(amount=str(Decimal(str(amount))), currency=currency)


# ── Client and product profiles (DCGSI Art. 4, Anexos 3 y 4) ──────────────────


class RiskCategory(StrEnum):
    CONSERVADOR = "conservador"
    MODERADO = "moderado"
    CRECIMIENTO = "crecimiento"
    AGRESIVO = "agresivo"


class RiskLevel(StrEnum):
    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"


class KnowledgeLevel(StrEnum):
    BASICO = "basico"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"


class Complexity(StrEnum):
    SIMPLE = "simple"
    MODERADA = "moderada"
    COMPLEJA = "compleja"


RISK_ORDER: dict[str, int] = {"bajo": 1, "medio": 2, "alto": 3}
#: Fixed mapping from docs/04-backend/03 §2 - the committee's, not the model's.
CATEGORY_MAX_RISK: dict[RiskCategory, RiskLevel] = {
    RiskCategory.CONSERVADOR: RiskLevel.BAJO,
    RiskCategory.MODERADO: RiskLevel.MEDIO,
    RiskCategory.CRECIMIENTO: RiskLevel.ALTO,
    RiskCategory.AGRESIVO: RiskLevel.ALTO,
}
KNOWLEDGE_ORDER: dict[str, int] = {"basico": 1, "intermedio": 2, "avanzado": 3}
COMPLEXITY_ORDER: dict[str, int] = {"simple": 1, "moderada": 2, "compleja": 3}


class InvestorProfile(BaseModel):
    """Perfil del inversionista - DCGSI Art. 4, Anexo 3.

    ``capacity_band`` is a band label; absolute net worth never reaches the
    model (docs/06-compliance/04 §9). Non-sophisticated is the default (Art. 2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile_id: str
    version: int
    risk_category: RiskCategory
    horizon_months: int = Field(ge=0)
    knowledge_level: KnowledgeLevel
    capacity_band: str = Field(description="Band label, never an absolute amount")
    objectives: list[str] = Field(default_factory=list)
    permitted_currencies: list[str] = Field(default_factory=lambda: ["MXN"])
    min_liquidity_pct: float = Field(default=0.0, ge=0.0, le=1.0)
    is_sophisticated: bool = False
    assessed_at: date
    expires_at: date

    @property
    def max_risk(self) -> RiskLevel:
        return CATEGORY_MAX_RISK[self.risk_category]

    @property
    def horizon_band(self) -> str:
        if self.horizon_months < 12:
            return "corto plazo"
        if self.horizon_months < 36:
            return "mediano plazo"
        return "largo plazo"

    def is_current(self, today: date) -> bool:
        return self.expires_at >= today


class ProductProfile(BaseModel):
    """Perfil del producto financiero - DCGSI Art. 4, Anexo 4, determined by
    the product analysis committee (Art. 20). The model never writes any of it
    (control IS-07)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str
    name: str
    committee_version: int
    risk_level: RiskLevel
    complexity: Complexity
    liquidity_hours: int | None
    min_holding_months: int = Field(ge=0)
    minimum_investment: Decimal
    currency: Literal["MXN", "USD", "EUR"]
    annual_cost_pct: float
    asset_class: str
    approved_at: date


# ── Suitability (razonabilidad, DCGSI Art. 5) ─────────────────────────────────


class SuitabilityOutcome(StrEnum):
    APTO = "APTO"
    APTO_CON_ADVERTENCIA = "APTO_CON_ADVERTENCIA"
    NO_APTO = "NO_APTO"


class SuitabilityEvaluation(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    product_profile_version: int
    outcome: SuitabilityOutcome
    rule_id: str | None
    rationale: str
    warnings: list[str] = Field(default_factory=list)


class SuitabilityReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict_id: str
    ruleset_version: int
    profile_id: str
    profile_version: int
    amount: str = "0"
    evaluated_at: datetime
    evaluations: list[SuitabilityEvaluation]
    signature: str
    signing_key_version: int = 1

    @property
    def approved_product_ids(self) -> list[str]:
        return [
            e.product_id for e in self.evaluations if e.outcome is not SuitabilityOutcome.NO_APTO
        ]

    @property
    def rejected_product_ids(self) -> list[str]:
        return [e.product_id for e in self.evaluations if e.outcome is SuitabilityOutcome.NO_APTO]


# ── Guardrails ────────────────────────────────────────────────────────────────


class GuardrailAction(StrEnum):
    PASS = "PASS"
    REWRITE = "REWRITE"
    BLOCK = "BLOCK"


class GuardrailVerdict(BaseModel):
    action: GuardrailAction
    violations: list[str] = Field(default_factory=list)
    redactions: int = 0
    injection_score: float = 0.0
    disclosures_injected: list[str] = Field(default_factory=list)
    disclosure_versions: dict[str, str] = Field(default_factory=dict)
    detail: str | None = None


# ── Provenance ────────────────────────────────────────────────────────────────


class ProvenanceEntry(BaseModel):
    """Binds a numeric fact to the tool result that produced it
    (docs/07-data-governance/03 §3). ``compliance_guard`` rejects any figure in
    ``speech`` or ``ui_payload`` without a matching entry."""

    model_config = ConfigDict(frozen=True)

    value: str
    tool: str
    path: str
    as_of: datetime | None = None


# ── Output: the closed UI component registry (docs/03-mobile/01 §4) ───────────

UIComponentType = Literal[
    "portfolio_summary",
    "portfolio_positions",
    "attribution_bars",
    "cash_summary",
    "product_list",
    "product_detail",
    "product_comparison",
    "quote_table",
    "news_list",
    "research_list",
    "calendar_list",
    "simulation_chart",
    "fee_breakdown",
    "transaction_list",
    "statement_link",
    "accounts_list",
    "services_guide",
    "suitability_summary",
    "warning_banner",
    "form_spec",
    "citations",
    "escalation_offer",
    "escalation_card",
    "complaint_card",
    "order_receipt",
    "disclosure",
    "profile_update_offer",
]

UI_COMPONENT_TYPES: frozenset[str] = frozenset(UIComponentType.__args__)  # type: ignore[attr-defined]


class UIComponent(BaseModel):
    """Every component carries ``source`` and ``as_of`` so the client can render
    staleness and an auditor can trace it (docs/07-data-governance/01 §5)."""

    model_config = ConfigDict(extra="forbid")

    type: UIComponentType
    payload: dict[str, Any]
    as_of: datetime | None = None
    source: str | None = None


class Citation(BaseModel):
    title: str
    url: str | None = None
    source: str
    published_at: datetime | None = None
    ref: str | None = None


class ToolResult(BaseModel):
    name: str
    ok: bool
    data: Any = None
    error: str | None = None
    latency_ms: int = 0
    cache_hit: bool = False
    as_of: datetime | None = None
    args_hash: str | None = None
    result_hash: str | None = None
    classification: str = "RESTRICTED"


class Entitlements(BaseModel):
    model_config = ConfigDict(frozen=True)

    contracted_for_advised_services: bool = False
    contracted_for_execution: bool = False
    permitted_product_families: list[str] = Field(default_factory=list)
    daily_avatar_minutes_remaining: int = 0


class AgentError(BaseModel):
    code: str
    message_es: str
    escalate: bool = False


# ── Form Spec (ADR-0009) ───────────────────────────────────────────────────────

FormFieldType = Literal["money", "select", "boolean", "date", "text", "acknowledgement"]
Operation = Literal["BUY", "SELL", "SWITCH", "REDEEM", "RECURRING"]


class FormField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")
    type: FormFieldType
    label: str
    required: bool = True
    currency: Literal["MXN", "USD", "EUR"] | None = None
    min: str | None = None
    max: str | None = None
    step: str | None = None
    help: str | None = None
    options: list[dict[str, str]] | None = None
    options_source: str | None = Field(default=None, pattern=r"^tool:[a-z_]+$")
    default: Any = None
    max_length: int | None = None


class FormDisclosure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: str
    text: str
    ack: bool = False


class FormExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cutoff_local: str
    timezone: str = "America/Mexico_City"
    settlement: str
    valuation: str


class FormProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    risk_level: RiskLevel
    currency: Literal["MXN", "USD", "EUR"]


class FormSpec(BaseModel):
    """Signed, single-use, 10-minute TTL. ``client_id`` is bound into the
    signature and compared with the token subject on submission."""

    model_config = ConfigDict(extra="forbid")

    form_id: str
    client_id: str
    thread_id: str
    turn_id: str
    operation: Operation
    product: FormProduct
    target_product: FormProduct | None = None
    suitability_verdict_id: str | None = None
    approved_amount: Money | None = None
    fields: list[FormField]
    disclosures: list[FormDisclosure]
    execution: FormExecution
    issued_at: datetime
    expires_at: datetime
    signature: str = ""
    signing_key_version: int = 1

    def required_acknowledgements(self) -> list[str]:
        return [d.id for d in self.disclosures if d.ack]


# ── Consents and disclosures (DCGSI Art. 24/26, LFPDPPP) ─────────────────────


class ConsentType(StrEnum):
    PRIVACY_NOTICE = "privacy_notice"
    SERVICES_GUIDE = "investment_services_guide"
    AI_ASSISTANT = "ai_disclosure"
    VOICE_RECORDING = "voice_recording"
    MODEL_IMPROVEMENT = "model_improvement"


#: Public ids used in ``disclosures_required`` (docs/04-backend/04 §2).
DISCLOSURE_PUBLIC_ID: dict[ConsentType, str] = {
    ConsentType.PRIVACY_NOTICE: "PRIVACY_NOTICE",
    ConsentType.SERVICES_GUIDE: "SERVICES_GUIDE",
    ConsentType.AI_ASSISTANT: "AI_ASSISTANT",
    ConsentType.VOICE_RECORDING: "VOICE_RECORDING",
    ConsentType.MODEL_IMPROVEMENT: "MODEL_IMPROVEMENT",
}
PUBLIC_ID_TO_CONSENT: dict[str, ConsentType] = {v: k for k, v in DISCLOSURE_PUBLIC_ID.items()}

#: Gate the first turn (Art. 24 guide + privacy notice + AI disclosure).
FIRST_TURN_CONSENTS: tuple[ConsentType, ...] = (
    ConsentType.PRIVACY_NOTICE,
    ConsentType.SERVICES_GUIDE,
    ConsentType.AI_ASSISTANT,
)


class ConsentRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_id: str
    type: ConsentType
    version: str
    granted: bool
    granted_at: datetime
    revoked_at: datetime | None = None
    channel: Literal["chat", "voice", "app"] = "app"


# ── The state ─────────────────────────────────────────────────────────────────


class AdvisorState(TypedDict, total=False):
    # identity - write-once at entry
    client_id: str
    first_name: str
    thread_id: str
    turn_id: str
    channel: Literal["voice", "chat"]
    locale: str
    register: Literal["tu", "usted"]

    # input
    messages: Annotated[list[AnyMessage], add_messages]
    client_input_text: str
    transcript_confidence: float | None
    audio_ref: str | None

    # routing
    intent: Intent
    intent_confidence: float
    intent_runner_up: Intent | None
    entitlements: Entitlements
    service_type: ServiceType
    service_subtype: str
    degraded_from: Intent | None
    profile_filtered: bool

    # working set
    investor_profile: InvestorProfile | None
    tool_results: dict[str, ToolResult]
    provenance: dict[str, ProvenanceEntry]
    candidate_products: list[ProductProfile]
    proposed_amount: Money | None
    tool_rounds: int
    tool_calls_made: int
    planned_calls: list[dict[str, Any]]
    needs_more_tools: bool
    stripped_products: list[ProductProfile]

    # verdicts
    suitability: SuitabilityReport | None
    guardrail_input: GuardrailVerdict | None
    guardrail_output: GuardrailVerdict | None
    rewrite_attempts: int

    # output
    speech: str | None
    ui_payload: list[UIComponent]
    citations: list[Citation]
    form_spec: FormSpec | None
    disclosures_shown: dict[str, str]
    disclosure_texts: dict[str, str]

    # model metadata for the evidence record
    model_meta: dict[str, Any]

    # transaction resume
    submission: dict[str, Any] | None
    receipt: dict[str, Any] | None

    # control
    filler_emitted: bool
    distress: bool
    error: AgentError | None
    evidence_id: str | None
    started_at: str


class IdentityViolation(RuntimeError):
    """Raised when a node attempts to change write-once identity fields."""


IDENTITY_FIELDS: tuple[str, ...] = ("client_id", "thread_id", "turn_id")


def assert_identity_unchanged(before: AdvisorState, after: AdvisorState) -> None:
    for field in IDENTITY_FIELDS:
        if field in before and field in after and before[field] != after[field]:  # type: ignore[literal-required]
            raise IdentityViolation(f"node attempted to modify write-once field {field}")


def normalise_figure(value: float | int | str) -> str:
    """Provenance keys are normalised so that 0.87, 0.870 and "0.87" collide."""
    return f"{float(value):.6g}"


class ValidatedMoneyPayload(BaseModel):
    """Helper used by tool result validators to reject bare monetary numbers."""

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def _no_bare_money(self) -> ValidatedMoneyPayload:
        for key, value in (self.model_extra or {}).items():
            if key.endswith(("_amount", "_value", "balance")) and isinstance(value, (int, float)):
                raise ValueError(f"{key} must be a Money object with an explicit currency")
        return self
