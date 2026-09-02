"""Tool result schemas - validated at the boundary before anything enters graph
state (docs/04-backend/03 §1: "Results are schema-validated before entering
graph state. A misbehaving upstream cannot inject content into the prompt").

Strict: a missing field is an error, not a ``None``; an unknown enum value fails
closed; a monetary value without an explicit currency is rejected, not defaulted
to MXN (docs/07-data-governance/03 §6).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from actinver_agent.graph.state import Complexity, Money, RiskLevel

_MONEY_KEYS = frozenset(
    {
        "amount",
        "market_value",
        "cost_basis",
        "available",
        "pending",
        "total",
        "minimum_investment",
        "period_return_amount",
        "total_market_value",
        "cash",
        "estimated_isr_withholding",
        "pessimistic",
        "base",
        "optimistic",
        "min",
        "max",
    }
)


def _reject_bare_money(node: Any, path: str = "") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            if (
                key in _MONEY_KEYS
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            ):
                raise ValueError(
                    f"{child}: monetary value must be {{amount, currency}}, got a bare number"
                )
            _reject_bare_money(value, child)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _reject_bare_money(value, f"{path}[{i}]")


class ToolPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: str

    @model_validator(mode="before")
    @classmethod
    def _no_bare_money(cls, data: Any) -> Any:
        if isinstance(data, dict):
            _reject_bare_money(data)
        return data


# ── Portfolio ──────────────────────────────────────────────────────────────────


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    name: str
    asset_class: str
    quantity: float
    market_value: Money
    #: Absent when the source system does not expose an acquisition price
    #: (the InvestmentOffice dataset forbids projecting ``precio``, trap T5).
    cost_basis: Money | None = None
    weight_pct: float
    currency: Literal["MXN", "USD", "EUR"]


class PositionsResult(ToolPayload):
    total_market_value: Money
    cash: Money
    liquid_pct: float = Field(ge=0.0, le=1.0)
    positions: list[Position]


class PerformanceResult(ToolPayload):
    period: str
    period_return_pct: float
    period_return_amount: Money
    market_value: Money
    valuation_date: str


class Contribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sleeve: str
    bps: int


class AttributionResult(ToolPayload):
    period: str
    granularity: Literal["asset_class", "product", "currency"]
    total_bps: int
    contributions: list[Contribution]


class Settlement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    amount: Money


class CashResult(ToolPayload):
    available: Money
    pending: Money
    settlements: list[Settlement]


class Account(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str
    label: str
    type: str
    currency: Literal["MXN", "USD", "EUR"]
    eligible_for: list[Literal["debit", "credit"]]


class AccountsResult(ToolPayload):
    accounts: list[Account]


class Operation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    date: str
    type: Literal["BUY", "SELL", "DIVIDEND", "FEE", "SWITCH", "REDEEM"]
    product_id: str
    amount: Money
    status: str


class HistoryResult(ToolPayload):
    items: list[Operation]


class StatementResult(ToolPayload):
    """A signed short-lived link. The document is never inlined."""

    year: int
    month: int
    url: str
    expires_at: str


# ── Products ───────────────────────────────────────────────────────────────────


class ProductSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    name: str
    risk_level: RiskLevel
    complexity: Complexity
    asset_class: str
    currency: Literal["MXN", "USD", "EUR"]
    liquidity_hours: int | None
    min_holding_months: int
    minimum_investment: Money
    annual_cost_pct: float
    committee_version: int
    historical_returns: list[HistoricalReturn] | None = None


class HistoricalReturn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: str
    return_pct: float
    as_of: str


class ProductSearchResult(ToolPayload):
    items: list[ProductSummary]


class Fees(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annual_cost_pct: float
    entry_fee_pct: float
    exit_fee_pct: float


class ProductDetailResult(ToolPayload):
    product_id: str
    name: str
    risk_level: RiskLevel
    complexity: Complexity
    asset_class: str
    currency: Literal["MXN", "USD", "EUR"]
    liquidity_hours: int | None
    min_holding_months: int
    minimum_investment: Money
    annual_cost_pct: float
    committee_version: int
    objective: str
    policy: str
    fees: Fees
    historical_returns: list[HistoricalReturn]
    dici_url: str
    prospectus_url: str


class ProductProfileResult(ToolPayload):
    product_id: str
    name: str
    committee_version: int
    risk_level: RiskLevel
    complexity: Complexity
    liquidity_hours: int | None
    min_holding_months: int
    minimum_investment: str
    currency: Literal["MXN", "USD", "EUR"]
    annual_cost_pct: float
    asset_class: str
    approved_at: str


class CompareResult(ToolPayload):
    items: list[ProductSummary] = Field(min_length=2, max_length=4)


class SuitabilityEvaluationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    product_profile_version: int
    outcome: Literal["APTO", "APTO_CON_ADVERTENCIA", "NO_APTO"]
    rule_id: str | None
    rationale: str
    warnings: list[str]


class SuitabilityResult(ToolPayload):
    verdict_id: str
    ruleset_version: int
    evaluations: list[SuitabilityEvaluationOut]
    signature: str


# ── Market and news ────────────────────────────────────────────────────────────


class Quote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    price: float
    currency: str
    change_pct: float
    timestamp: str
    delayed: bool
    delay_minutes: int


class QuotesResult(ToolPayload):
    quotes: list[Quote]


class NewsItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    source: str
    published_at: str
    summary: str


class NewsResult(ToolPayload):
    items: list[NewsItem]


class CalendarEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    region: Literal["MX", "US", "GLOBAL"]
    name: str
    importance: Literal["alta", "media", "baja"]


class CalendarResult(ToolPayload):
    events: list[CalendarEvent]


# ── Simulation, fees, requirements ────────────────────────────────────────────


class Scenarios(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pessimistic: Money
    base: Money
    optimistic: Money


class SimulationResult(ToolPayload):
    product_id: str
    amount: Money
    horizon_months: int
    annual_volatility_pct: float
    scenarios: Scenarios
    disclosures: list[str]

    @model_validator(mode="after")
    def _mandatory_disclosure(self) -> SimulationResult:
        if "SIMULATION_NOT_PROMISE" not in self.disclosures:
            raise ValueError("simulation results must carry SIMULATION_NOT_PROMISE")
        return self


class FeeLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    amount: Money


class FeesResult(ToolPayload):
    fees: list[FeeLine]
    estimated_isr_withholding: Money
    total: Money
    disclosures: list[str]


class RequirementsProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    risk_level: RiskLevel
    currency: Literal["MXN", "USD", "EUR"]


class RequirementsDisclosure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    ack: bool


class RequirementsExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cutoff_local: str
    timezone: str
    settlement: str
    valuation: str


class RequirementsLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min: Money
    max: Money


class RequirementsResult(ToolPayload):
    operation: Literal["BUY", "SELL", "SWITCH", "REDEEM", "RECURRING"]
    product: RequirementsProduct
    target_product: RequirementsProduct | None = None
    fields: list[dict[str, Any]]
    disclosures: list[RequirementsDisclosure]
    execution: RequirementsExecution
    limits: RequirementsLimits


# ── Support ────────────────────────────────────────────────────────────────────


class EscalationResult(ToolPayload):
    case_id: str
    sla: str
    promotor_name: str
    reason: str


class ComplaintResult(ToolPayload):
    folio: str
    category: str
    response_deadline: str
    condusef_notice: str


class GuideSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    text: str


class GuideResult(ToolPayload):
    version: str
    section: str
    sections: list[GuideSection]
    download_url: str


class ClientContextResult(ToolPayload):
    first_name: str
    register: Literal["tu", "usted"]
    risk_category: str
    entitlements: dict[str, Any]
    promotor: dict[str, str]


class InvestorProfileResult(ToolPayload):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    version: int
    risk_category: str
    horizon_months: int
    knowledge_level: str
    capacity_band: str
    objectives: list[str]
    permitted_currencies: list[str]
    min_liquidity_pct: float
    is_sophisticated: bool
    assessed_at: str
    expires_at: str
