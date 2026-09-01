"""Tool registry.

Design rules, all of which are load-bearing:

1. **``client_id`` is never a model-supplied argument.** It is injected from the
   validated request context. If the model attempts to supply one, the registry
   strips it and logs a security event (docs/05-security/02 §4.1). The model
   literally cannot name a client (ADR-0014).
2. **No tool mutates state.** ``mutating`` must be False for every spec;
   ``register`` refuses otherwise, and a CI assertion walks the registry
   (control AI-05, ADR-0010).
3. **Every result is schema-validated** before it enters graph state.
4. **Every numeric scalar in a result is registered in the provenance map** so
   ``compliance_guard`` can prove where each figure came from (control AI-03).
5. **Tools are visible per intent**, not globally (``INTENT_TOOL_MAP``).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import orjson
import structlog
from pydantic import BaseModel, ConfigDict, ValidationError

from actinver_agent.graph.state import ProvenanceEntry, ToolResult, normalise_figure
from actinver_agent.observability.setup import get_metrics

log = structlog.get_logger(__name__)

ToolFn = Callable[..., Awaitable[Any]]
_TEXT_FIGURE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")


class ToolArgs(BaseModel):
    """Base for every argument schema: closed, no extras (threat model LLM07)."""

    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description_es: str
    args_schema: type[BaseModel]
    fn: ToolFn
    #: Whether the runner injects ``client_id`` from the request context.
    requires_client: bool = True
    #: Data classification of the result. RESTRICTED never reaches the model raw.
    classification: str = "RESTRICTED"
    timeout_s: float = 3.0
    cache_ttl_s: int = 0
    #: Regulatory service classification this tool participates in.
    service_type: str = "no_asesorado"
    tags: tuple[str, ...] = ()
    #: Must always be False. Execution lives in transaction-service (ADR-0010).
    mutating: bool = False
    #: News/market context fail open (answer without them); positions and the
    #: profile fail closed (docs/04-backend/02 §3).
    fail_open: bool = False
    result_model: type[BaseModel] | None = None
    #: Retrieved third-party text - wrapped and scanned before the model sees it.
    untrusted_content: bool = False


class MutatingToolError(ValueError):
    pass


@dataclass
class ToolRegistry:
    _tools: dict[str, ToolSpec] = field(default_factory=dict)

    def register(self, spec: ToolSpec) -> None:
        if spec.mutating:
            raise MutatingToolError(
                f"tool {spec.name} declares mutating=True; no tool may move money or "
                "place an order (ADR-0010)"
            )
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool registration: {spec.name}")
        if "client_id" in spec.args_schema.model_fields:
            raise ValueError(f"tool {spec.name} must not accept client_id as an argument")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def allowed_for(self, intent: str) -> tuple[str, ...]:
        return INTENT_TOOL_MAP.get(intent, ())

    def declarations_for(self, intent: str) -> list[dict[str, Any]]:
        """Gemini function declarations, filtered to the tools this intent may
        use. Narrowing the tool surface per intent shrinks the injection
        surface and improves routing accuracy."""
        allowed = self.allowed_for(intent)
        return [
            {
                "name": spec.name,
                "description": spec.description_es,
                "parameters": _strip_injected(spec),
            }
            for name, spec in self._tools.items()
            if name in allowed
        ]

    async def call(
        self,
        name: str,
        *,
        client_id: str | None,
        args: dict[str, Any],
        timeout_s: float | None = None,
    ) -> ToolResult:
        spec = self.get(name)
        args = dict(args)
        if "client_id" in args:
            # The model attempted to supply a client identifier. This is either
            # a bug or an attack; either way the value is discarded and logged.
            log.warning("tool.client_id_from_model", tool=name, security_event=True)
            get_metrics().tool_errors.add(1, {"tool": name, "reason": "client_id_from_model"})
            args.pop("client_id")

        started = time.perf_counter()
        try:
            validated = spec.args_schema.model_validate(args)
        except ValidationError as exc:
            log.warning("tool.invalid_args", tool=name, errors=exc.error_count())
            return ToolResult(
                name=name,
                ok=False,
                error="INVALID_ARGS",
                classification=spec.classification,
                args_hash=_hash(args),
            )
        call_kwargs = validated.model_dump(exclude_none=True, mode="json")
        args_hash = _hash(call_kwargs)
        if spec.requires_client:
            if client_id is None:
                raise ValueError(f"{name} requires a client context")
            call_kwargs["client_id"] = client_id

        try:
            data = await asyncio.wait_for(
                spec.fn(**call_kwargs), timeout=timeout_s or spec.timeout_s
            )
            if spec.result_model is not None:
                data = spec.result_model.model_validate(data).model_dump(
                    mode="json", exclude_none=True
                )
            latency = int((time.perf_counter() - started) * 1000)
            get_metrics().tool_latency_ms.record(latency, {"tool": name})
            get_metrics().tool_calls.add(1, {"tool": name, "status": "ok"})
            return ToolResult(
                name=name,
                ok=True,
                data=data,
                latency_ms=latency,
                as_of=_parse_as_of(data),
                args_hash=args_hash,
                result_hash=_hash(data),
                classification=spec.classification,
            )
        except TimeoutError:
            error = "TIMEOUT"
        except ValidationError as exc:
            log.warning("tool.invalid_result", tool=name, errors=exc.error_count())
            error = "INVALID_RESULT"
        except Exception as exc:
            log.warning("tool.failed", tool=name, error=type(exc).__name__)
            error = type(exc).__name__
        latency = int((time.perf_counter() - started) * 1000)
        get_metrics().tool_calls.add(1, {"tool": name, "status": "error"})
        get_metrics().tool_errors.add(1, {"tool": name, "reason": error})
        return ToolResult(
            name=name,
            ok=False,
            error=error,
            latency_ms=latency,
            args_hash=args_hash,
            classification=spec.classification,
        )


def _strip_injected(spec: ToolSpec) -> dict[str, Any]:
    schema = spec.args_schema.model_json_schema()
    schema.get("properties", {}).pop("client_id", None)
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r != "client_id"]
    schema.pop("title", None)
    return schema


def _hash(data: Any) -> str:
    return hashlib.sha256(orjson.dumps(data, option=orjson.OPT_SORT_KEYS, default=str)).hexdigest()


def _parse_as_of(data: Any) -> datetime | None:
    if isinstance(data, dict) and isinstance(data.get("as_of"), str):
        try:
            return datetime.fromisoformat(data["as_of"])
        except ValueError:
            return None
    return None


def record_provenance(
    result: ToolResult, into: dict[str, ProvenanceEntry], prefix: str = ""
) -> None:
    """Walk a tool result and register every numeric scalar.

    ``compliance_guard`` later asserts that every figure appearing in the
    response exists here. A figure that does not is, by definition, invented.

    Money amounts are decimal *strings* and are registered too. For every
    figure the speech-safe rounded forms (``1.2`` for 1,247,318.44 → "1.2
    millones", ``18`` for 18,450 → "18 mil", one-decimal percentages) are also
    registered, so a correctly rounded spoken figure traces back to its source
    while an invented one still fails.
    """

    def register(value: float, path: str) -> None:
        for key in derived_keys(value):
            into.setdefault(
                key,
                ProvenanceEntry(
                    value=str(value),
                    tool=result.name,
                    path=path,
                    as_of=result.as_of,
                ),
            )

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            is_money = set(node) == {"amount", "currency"}
            for k, v in node.items():
                child = f"{path}.{k}" if path else k
                if is_money and k == "amount":
                    try:
                        register(float(Decimal(str(v))), child)
                    except (InvalidOperation, ValueError):
                        continue
                else:
                    walk(v, child)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            register(float(node), path)
        elif isinstance(node, str):
            # Figures quoted inside tool text (a headline saying "25 pb", a DICI
            # saying "0.85 por ciento") are sourced too: they came from the tool.
            for raw in _TEXT_FIGURE.findall(node):
                try:
                    register(float(raw.replace(",", "")), path)
                except ValueError:
                    continue

    walk(result.data, prefix)


def derived_keys(value: float) -> list[str]:
    keys = [normalise_figure(value)]
    if value < 0:
        # "menos 0.9 por ciento" is the same fact as -0.9: register the magnitude too.
        keys.extend(derived_keys(-value))
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        keys.append(normalise_figure(round(value / 1_000_000, 1)))
        keys.append(normalise_figure(round(value / 1_000_000, 2)))
    if magnitude >= 1_000:
        keys.append(normalise_figure(round(value / 1_000, 0)))
        keys.append(normalise_figure(round(value / 1_000, 1)))
    keys.append(normalise_figure(round(value, 1)))
    keys.append(normalise_figure(round(value, 0)))
    if magnitude < 100:
        keys.append(normalise_figure(round(value, 2)))
    return keys


# Tools each intent may reach. Anything not listed is unreachable for that turn.
INTENT_TOOL_MAP: dict[str, tuple[str, ...]] = {
    "portfolio_inspect": (
        "get_portfolio_positions",
        "get_portfolio_performance",
        "get_cash_balance",
        "get_client_accounts",
    ),
    "portfolio_explain": (
        "get_portfolio_positions",
        "get_portfolio_performance",
        "get_portfolio_attribution",
        "search_market_news",
        "get_market_quote",
        "get_economic_calendar",
        "get_actinver_research",
    ),
    "market_context": (
        "search_market_news",
        "get_market_quote",
        "get_economic_calendar",
        "get_actinver_research",
    ),
    "product_discover": (
        "search_investment_products",
        "get_product_detail",
        "compare_products",
        "get_product_risk_profile",
    ),
    "advisory_recommend": (
        "get_investor_profile",
        "get_portfolio_positions",
        "search_investment_products",
        "get_product_detail",
        "get_product_risk_profile",
        "check_suitability",
    ),
    "simulate": (
        "get_product_detail",
        "simulate_investment",
        "calculate_fees_and_taxes",
    ),
    "transact_buy": (
        "get_product_detail",
        "check_suitability",
        "get_transaction_requirements",
        "get_client_accounts",
        "get_cash_balance",
    ),
    "transact_sell": (
        "get_portfolio_positions",
        "get_transaction_requirements",
        "calculate_fees_and_taxes",
    ),
    "transact_switch": (
        "get_portfolio_positions",
        "get_product_detail",
        "check_suitability",
        "get_transaction_requirements",
    ),
    "transact_redeem": (
        "get_portfolio_positions",
        "get_transaction_requirements",
        "calculate_fees_and_taxes",
    ),
    "account_admin": (
        "get_transaction_history",
        "get_account_statements",
        "get_client_accounts",
        "get_investment_services_guide",
    ),
    "profile_update": ("get_investor_profile",),
    "escalate": ("escalate_to_advisor",),
    "complaint": ("file_complaint",),
}
