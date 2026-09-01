"""Deterministic model bindings.

Three roles:

* The **rules-only path** for Phase 1 (docs/01-architecture/06 §3.1) and the
  local / CI stack: no credentials, no network, reproducible.
* The **deterministic fallback** when the model provider is unavailable
  (docs/01-architecture/01 §7; runbook RB-09): templated responses over tool
  results for the informational intents; everything else escalates.
* A **reference implementation** of the contract Gemini adapters must honour:
  the model proposes, never approves; speech never carries exact figures.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from actinver_agent.graph.state import (
    ADVISORY_INTENTS,
    TRANSACTIONAL_INTENTS,
    AdvisorState,
    Intent,
)
from actinver_agent.llm.speech_format import direction_word, speech_safe_amount, speech_safe_percent
from actinver_agent.ports import ClassificationResult, GenerationResult, ToolCall
from actinver_agent.tools.registry import INTENT_TOOL_MAP

# ── Router ─────────────────────────────────────────────────────────────────────

_RULES: list[tuple[Intent, float, list[str]]] = [
    (
        Intent.ESCALATE,
        0.95,
        [
            r"hablar con (una persona|alguien|mi asesor|un asesor|un humano)",
            r"\bpromotor\b",
            r"comun[ií]came",
            r"\bfraude\b",
            r"no reconozco",
        ],
    ),
    (
        Intent.COMPLAINT,
        0.9,
        [
            r"\breclam",
            r"\bqueja\b",
            r"no estoy de acuerdo con (un|el) cargo",
            r"\bcondusef\b",
            r"\bune\b",
        ],
    ),
    (
        Intent.PROFILE_UPDATE,
        0.9,
        [r"(cambiar|actualizar) mi perfil", r"perfil de riesgo", r"cuestionario de perfil"],
    ),
    (
        Intent.TRANSACT_SWITCH,
        0.85,
        [r"\bcambiar(me)? de fondo", r"\btraspas", r"\bmover .* (a|al) (fondo|otro)"],
    ),
    (
        Intent.TRANSACT_REDEEM,
        0.85,
        [r"\brescat", r"\bredimir", r"\bretirar (todo|mi dinero|el saldo)"],
    ),
    (Intent.TRANSACT_SELL, 0.85, [r"\bvender\b", r"\bvendo\b", r"\bretirar\b", r"\bretiro\b"]),
    (
        Intent.TRANSACT_BUY,
        0.85,
        [
            r"\bquiero (comprar|invertir|meter|poner)",
            r"\bcomprar\b",
            r"\binvertir (en|los|\d)",
            r"\bmét(e|a)le\b",
            r"\baportar\b",
            r"\bhacerlo mensual",
            r"\bcontratar\b",
        ],
    ),
    (
        Intent.SIMULATE,
        0.85,
        [
            r"\bsimul",
            r"\bcu[aá]nto (crecer[ií]a|tendr[ií]a|ganar[ií]a)",
            r"\bqu[eé] pasa si",
            r"\bproyect",
            r"\ben \d+ a[nñ]os\b",
            r"\bescenario",
        ],
    ),
    (
        Intent.ADVISORY_RECOMMEND,
        0.9,
        [
            r"\bme conviene",
            r"\bd[oó]nde (invierto|meto|pongo)",
            r"\bqu[eé] me recomiendas",
            r"\brecom(i[eé]ndame|endaci[oó]n)",
            r"\bpara m[ií]\b",
            r"\bmi situaci[oó]n",
            r"\bmi caso",
            r"\bcu[aá]l (es mejor|me conviene|elijo|escojo)",
        ],
    ),
    (
        Intent.PRODUCT_DISCOVER,
        0.8,
        [
            r"\bqu[eé] (fondos|productos|opciones|instrumentos)",
            r"\bfondos? (de|con|hay)",
            r"\bbajo riesgo",
            r"\bproductos?\b",
            r"\bcompar(a|ar)\b",
            r"\bDICI\b",
            r"\bprospecto",
        ],
    ),
    (
        Intent.ACCOUNT_ADMIN,
        0.85,
        [
            r"\bestado de cuenta",
            r"\bcu[aá]ndo liquida",
            r"\bmovimientos",
            r"\bhistorial",
            r"\bgu[ií]a de servicios",
            r"\bcomisiones\b",
            r"\bmis cuentas",
            r"\bcontrato\b",
            r"\bhorario",
        ],
    ),
    (
        Intent.PORTFOLIO_EXPLAIN,
        0.85,
        [
            r"\bpor qu[eé]\b",
            r"\bbaj[oó]\b",
            r"\bsubi[oó]\b",
            r"\bcay[oó]\b",
            r"\bperd[ií]\b",
            r"\bexpl[ií]ca",
            r"\bqu[eé] pas[oó] con mi",
        ],
    ),
    (
        Intent.MARKET_CONTEXT,
        0.8,
        [
            r"\bpeso\b",
            r"\bd[oó]lar",
            r"\btipo de cambio",
            r"\bbolsa\b",
            r"\bmercado",
            r"\bbanxico",
            r"\btasas?\b",
            r"\bcetes\b",
            r"\binflaci[oó]n",
            r"\bfed\b",
            r"\bqu[eé] (est[aá] )?pasa(ndo)? con",
        ],
    ),
    (
        Intent.PORTFOLIO_INSPECT,
        0.85,
        [
            r"\bcu[aá]nto tengo",
            r"\bc[oó]mo va(n)? mi",
            r"\bmi portafolio",
            r"\bmi saldo",
            r"\bmis (posiciones|inversiones|fondos)",
            r"\bcu[aá]nto (vale|hay|dinero)",
            r"\brendimiento\b",
            r"\bganancia",
            r"\befectivo",
            r"\bdisponible",
        ],
    ),
]

_OFF_TOPIC = [
    r"\bpol[ií]tic",
    r"\bm[eé]dic",
    r"\bdoctor",
    r"\breceta\b",
    r"\bf[uú]tbol",
    r"\bclima\b",
    r"\bchiste",
    r"\bpoema",
    r"\breligi",
    r"\belecci[oó]n",
]
_PORTFOLIO_MARKERS = [r"\bmi\b", r"\bmis\b", r"\btengo\b", r"\bportafolio\b", r"\bfondo de deuda\b"]


class RulesIntentClassifier:
    """Closed-set intent classification with keyword rules and an explicit
    bias toward ``advisory_recommend`` on ambiguity (docs/01-architecture/06 §3.2)."""

    async def classify(self, *, text: str, history: list[str], locale: str) -> ClassificationResult:  # noqa: ARG002
        lowered = text.lower()
        scores: dict[Intent, float] = {}
        for intent, base, patterns in _RULES:
            hits = sum(1 for p in patterns if re.search(p, lowered))
            if hits:
                scores[intent] = min(0.99, base + 0.04 * (hits - 1))
        if (
            Intent.MARKET_CONTEXT in scores
            and any(re.search(m, lowered) for m in _PORTFOLIO_MARKERS)
            and (Intent.PORTFOLIO_EXPLAIN in scores or "fondo" in lowered)
        ):
            # "¿qué pasó con mi fondo?" is about the portfolio, not the market.
            scores[Intent.PORTFOLIO_EXPLAIN] = max(scores.get(Intent.PORTFOLIO_EXPLAIN, 0), 0.86)
            scores[Intent.MARKET_CONTEXT] -= 0.1
        if not scores:
            if any(re.search(p, lowered) for p in _OFF_TOPIC) or len(lowered.split()) < 2:
                return ClassificationResult(Intent.OUT_OF_SCOPE, 0.9)
            return ClassificationResult(
                Intent.OUT_OF_SCOPE, 0.55, runner_up=Intent.PORTFOLIO_INSPECT
            )

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        intent, confidence = ranked[0]
        runner_up = ranked[1][0] if len(ranked) > 1 else None
        profile_filtered = False
        if intent is Intent.PRODUCT_DISCOVER:
            profile_filtered = bool(
                re.search(r"\b(me conviene|para m[ií]|mi perfil|seg[uú]n mi)\b", lowered)
            )
            if profile_filtered or (runner_up is Intent.ADVISORY_RECOMMEND):
                # Profile-matched discovery is a regulated advisory act.
                intent, runner_up = Intent.ADVISORY_RECOMMEND, Intent.PRODUCT_DISCOVER
                profile_filtered = True
        if intent is Intent.SIMULATE and Intent.ADVISORY_RECOMMEND in scores:
            intent, runner_up = Intent.ADVISORY_RECOMMEND, Intent.SIMULATE
        if intent is Intent.ADVISORY_RECOMMEND:
            profile_filtered = True
        return ClassificationResult(
            intent,
            round(confidence, 2),
            runner_up=runner_up,
            profile_filtered=profile_filtered,
            model="rules",
        )


# ── Planner ────────────────────────────────────────────────────────────────────

_PERIODS: list[tuple[str, str]] = [
    (r"\b(este|del) mes\b|\bmensual\b|\bel mes\b", "MTD"),
    (r"\btrimestre\b", "QTD"),
    (r"\b(este|del|en el|el) a[nñ]o\b|\banual\b|\ben lo que va del a[nñ]o", "YTD"),
    (r"\b(12|doce) meses\b|\b[uú]ltimo a[nñ]o\b|\b1 ?a[nñ]o\b", "1Y"),
    (r"\b(3|tres) a[nñ]os\b", "3Y"),
]

_AMOUNT_RE = re.compile(
    r"(?P<num>\d{1,3}(?:[.,]\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)\s*(?P<unit>millones|mill[oó]n|mil)?",
    re.IGNORECASE,
)
_HORIZON_RE = re.compile(r"(?P<n>\d+)\s*(?P<u>a[nñ]os?|meses?)", re.IGNORECASE)


def extract_amount(text: str) -> Decimal | None:
    lowered = text.lower()
    best: Decimal | None = None
    for match in _AMOUNT_RE.finditer(lowered):
        raw = match.group("num")
        unit = match.group("unit")
        # Skip values that are clearly a period/horizon ("3 años", "12 meses") or a percentage.
        tail = lowered[match.end() : match.end() + 8]
        if re.match(r"\s*(a[nñ]os?|meses?|%|por ciento|d[ií]as?)", tail):
            continue
        cleaned = raw.replace(",", "") if re.search(r"\d,\d{3}", raw) else raw.replace(",", ".")
        try:
            value = Decimal(cleaned)
        except InvalidOperation:
            continue
        if unit:
            value *= Decimal("1000000") if unit.startswith("mill") else Decimal("1000")
        if value >= 100 and (best is None or value > best):
            best = value
    return best


def extract_period(text: str, default: str = "MTD") -> str:
    lowered = text.lower()
    for pattern, period in _PERIODS:
        if re.search(pattern, lowered):
            return period
    return default


def extract_horizon_months(text: str) -> int | None:
    match = _HORIZON_RE.search(text.lower())
    if not match:
        return None
    n = int(match.group("n"))
    return n * 12 if match.group("u").startswith("a") else n


def extract_product_ids(text: str, known: list[str]) -> list[str]:
    upper = text.upper()
    return [pid for pid in known if pid in upper or pid.split("-")[0] in upper]


class IntentPlanner:
    """Deterministic tool plan per intent, restricted to ``INTENT_TOOL_MAP``."""

    def __init__(self, known_products: list[str] | None = None) -> None:
        self._known = known_products or []

    async def plan(
        self, *, state: AdvisorState, declarations: list[dict[str, Any]]
    ) -> list[ToolCall]:
        intent = state.get("intent", Intent.OUT_OF_SCOPE)
        text = state.get("client_input_text", "")
        allowed = {d["name"] for d in declarations} & set(INTENT_TOOL_MAP.get(str(intent), ()))
        amount = state.get("proposed_amount")
        amount_dec = amount.decimal if amount is not None else extract_amount(text)
        products = extract_product_ids(text, self._known)
        period = extract_period(text)
        calls: list[ToolCall] = []

        def add(name: str, **args: Any) -> None:
            if name in allowed and all(c.name != name for c in calls):
                calls.append(ToolCall(name, {k: v for k, v in args.items() if v is not None}))

        if intent is Intent.PORTFOLIO_INSPECT:
            add("get_portfolio_positions")
            add("get_portfolio_performance", period=period)
            if re.search(r"efectivo|disponible|liquidez|saldo", text.lower()):
                add("get_cash_balance")
        elif intent is Intent.PORTFOLIO_EXPLAIN:
            add("get_portfolio_performance", period=period)
            add(
                "get_portfolio_attribution",
                period=period if period in {"MTD", "QTD", "YTD", "1Y"} else "MTD",
            )
            add("search_market_news", query=_news_query(text), limit=3)
            add("get_actinver_research", query=_news_query(text), limit=2)
        elif intent is Intent.MARKET_CONTEXT:
            add("search_market_news", query=_news_query(text), limit=4)
            add("get_market_quote", symbols=_symbols(text))
            add("get_economic_calendar", regions=["MX", "US"])
        elif intent is Intent.PRODUCT_DISCOVER:
            add("search_investment_products", **_product_filters(text))
            for pid in products[:2]:
                add("get_product_detail", product_id=pid)
            if len(products) >= 2:
                add("compare_products", product_ids=products[:4])
        elif intent is Intent.ADVISORY_RECOMMEND:
            add("get_investor_profile")
            add("get_portfolio_positions")
            add("search_investment_products", **_product_filters(text, state))
        elif intent is Intent.SIMULATE:
            pid = products[0] if products else "ACTIGOB-BF"
            add("get_product_detail", product_id=pid)
            add(
                "simulate_investment",
                product_id=pid,
                amount=str(amount_dec or Decimal("50000")),
                horizon_months=extract_horizon_months(text) or 36,
            )
        elif intent in TRANSACTIONAL_INTENTS:
            pid = products[0] if products else _last_mentioned_product(state) or "ACTIGOB-BF"
            operation = {
                Intent.TRANSACT_BUY: "BUY",
                Intent.TRANSACT_SELL: "SELL",
                Intent.TRANSACT_SWITCH: "SWITCH",
                Intent.TRANSACT_REDEEM: "REDEEM",
            }[intent]
            if intent is Intent.TRANSACT_BUY and re.search(
                r"mensual|recurrente|cada mes", text.lower()
            ):
                operation = "RECURRING"
            add("get_product_detail", product_id=pid)
            if intent in (Intent.TRANSACT_SELL, Intent.TRANSACT_REDEEM, Intent.TRANSACT_SWITCH):
                add("get_portfolio_positions")
            add(
                "get_transaction_requirements",
                product_id=pid,
                operation=operation,
                amount=str(amount_dec) if amount_dec else None,
                target_product_id=products[1]
                if intent is Intent.TRANSACT_SWITCH and len(products) > 1
                else None,
            )
            add("get_client_accounts")
            if intent is Intent.TRANSACT_BUY:
                add("get_cash_balance")
            if intent in (Intent.TRANSACT_SELL, Intent.TRANSACT_REDEEM) and amount_dec:
                add(
                    "calculate_fees_and_taxes",
                    product_id=pid,
                    operation=operation,
                    amount=str(amount_dec),
                )
        elif intent is Intent.ACCOUNT_ADMIN:
            lowered = text.lower()
            if "estado de cuenta" in lowered:
                from datetime import date

                today = date.today()
                month = today.month - 1 or 12
                year = today.year if today.month > 1 else today.year - 1
                add("get_account_statements", year=year, month=month)
            if re.search(r"movimientos|historial|operaciones", lowered):
                add("get_transaction_history", limit=10)
            if re.search(r"gu[ií]a|comisiones|servicios|reclamaci", lowered):
                add("get_investment_services_guide", section="completa")
            if re.search(r"cuentas?|contrato|liquida", lowered):
                add("get_client_accounts")
            if not calls:
                add("get_client_accounts")
        elif intent is Intent.PROFILE_UPDATE:
            add("get_investor_profile")
        elif intent is Intent.ESCALATE:
            urgency = (
                "immediate" if re.search(r"fraude|no reconozco|urgente", text.lower()) else "normal"
            )
            reason = "fraud_report" if urgency == "immediate" else "client_request"
            add("escalate_to_advisor", reason=reason, summary_es=text[:900], urgency=urgency)
        elif intent is Intent.COMPLAINT:
            category = "cargo_no_reconocido" if "cargo" in text.lower() else "servicio"
            add("file_complaint", category=category, description_es=text[:1900])
        return calls[:10]


def _news_query(text: str) -> str:
    words = [
        w
        for w in re.findall(r"[a-záéíóúñ]{4,}", text.lower())
        if w
        not in {
            "pasó",
            "paso",
            "está",
            "esta",
            "pasando",
            "porque",
            "para",
            "sobre",
            "cómo",
            "como",
            "cuánto",
            "cuanto",
            "tengo",
            "portafolio",
            "fondo",
            "bajó",
            "bajo",
            "subió",
            "subio",
            "quiero",
            "saber",
            "explica",
            "explícame",
        }
    ]
    return " ".join(words[:5]) or "mercado México"


def _symbols(text: str) -> list[str]:
    lowered = text.lower()
    symbols: list[str] = []
    if re.search(r"peso|d[oó]lar|tipo de cambio", lowered):
        symbols.append("USDMXN")
    if re.search(r"bolsa|ipc|bmv|acciones", lowered):
        symbols.append("IPC")
    if re.search(r"cetes|tasa", lowered):
        symbols.append("CETES28")
    if re.search(r"tiie", lowered):
        symbols.append("TIIE28")
    return symbols or ["USDMXN", "IPC"]


def _product_filters(text: str, state: AdvisorState | None = None) -> dict[str, Any]:
    lowered = text.lower()
    filters: dict[str, Any] = {"limit": 8}
    if re.search(r"bajo riesgo|conservador|seguro|sin riesgo|poco riesgo", lowered):
        filters["risk_level"] = ["bajo"]
    elif re.search(r"riesgo medio|moderado", lowered):
        filters["risk_level"] = ["bajo", "medio"]
    elif re.search(r"alto riesgo|agresivo|renta variable|acciones", lowered):
        filters["risk_level"] = ["alto"]
    if re.search(r"d[oó]lares|usd", lowered):
        filters["currency"] = "USD"
    horizon = extract_horizon_months(text)
    if horizon:
        filters["horizon_months_max"] = horizon
    profile = state.get("investor_profile") if state else None
    if profile is not None and "risk_level" not in filters:
        ceiling = {"bajo": ["bajo"], "medio": ["bajo", "medio"], "alto": ["bajo", "medio", "alto"]}
        filters["risk_level"] = ceiling[str(profile.max_risk)]
        filters.setdefault("horizon_months_max", profile.horizon_months)
    return filters


def _last_mentioned_product(state: AdvisorState) -> str | None:
    for result in reversed(list(state.get("tool_results", {}).values())):
        data = result.data if isinstance(result.data, dict) else {}
        items = data.get("items") or []
        if items and isinstance(items[0], dict) and "product_id" in items[0]:
            return str(items[0]["product_id"])
        if "product_id" in data:
            return str(data["product_id"])
    return None


# ── Generator ──────────────────────────────────────────────────────────────────


class TemplateGenerator:
    """Templated es-MX narrative over tool results. Never speaks exact figures,
    identifiers or a stripped product; proposes candidates, never approves."""

    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        *,
        state: AdvisorState,
        system_prompt: str,
        model: str,
        max_tokens: int,
        rewrite_hint: str | None,
    ) -> GenerationResult:
        self.calls += 1
        intent = state.get("intent", Intent.OUT_OF_SCOPE)
        results = {
            k: v.data
            for k, v in state.get("tool_results", {}).items()
            if v.ok and isinstance(v.data, dict)
        }
        failed = [k for k, v in state.get("tool_results", {}).items() if not v.ok]
        degraded = state.get("degraded_from") is not None
        name = state.get("first_name") or ""
        sentences: list[str] = []
        candidates: list[str] = []

        if intent is Intent.PORTFOLIO_INSPECT:
            sentences += self._inspect(results, name)
        elif intent is Intent.PORTFOLIO_EXPLAIN:
            sentences += self._explain(results)
        elif intent is Intent.MARKET_CONTEXT:
            sentences += self._market(results)
        elif intent in (Intent.PRODUCT_DISCOVER, Intent.ADVISORY_RECOMMEND):
            sentences, candidates = self._products(results, intent, degraded, state)
        elif intent is Intent.SIMULATE:
            sentences += self._simulate(results)
        elif intent in TRANSACTIONAL_INTENTS:
            sentences += self._transaction(results, intent)
        elif intent is Intent.ACCOUNT_ADMIN:
            sentences += self._admin(results)
        elif intent is Intent.PROFILE_UPDATE:
            sentences.append(
                "Tu perfil de inversionista se actualiza con un cuestionario breve que te dejo en pantalla."
            )
            sentences.append("Si prefieres, tu asesor puede acompañarte en el proceso.")
        elif intent is Intent.ESCALATE:
            esc = results.get("escalate_to_advisor")
            if esc:
                sentences.append(f"Le paso la conversación a {esc['promotor_name']}.")
                sentences.append(
                    f"Te contacta en {esc['sla']}; el número de caso queda en pantalla."
                )
            else:
                sentences.append("Te comunico con tu asesor en cuanto sea posible.")
        elif intent is Intent.COMPLAINT:
            comp = results.get("file_complaint")
            if comp:
                sentences.append(
                    "Registré tu reclamación ante la Unidad Especializada de Atención a Usuarios."
                )
                sentences.append(
                    "El folio y el plazo de respuesta quedan en pantalla, y tienes derecho a acudir a la CONDUSEF."
                )
            else:
                sentences.append(
                    "No pude registrar la reclamación en este momento; te comunico con tu asesor."
                )
        else:
            sentences.append("Sólo puedo ayudarte con temas de tus inversiones en Actinver.")
            sentences.append("¿Qué te gustaría saber de tu portafolio?")

        if failed and intent not in (Intent.ESCALATE, Intent.COMPLAINT):
            if any(
                f
                in {"get_portfolio_positions", "get_portfolio_performance", "get_investor_profile"}
                for f in failed
            ):
                sentences = [
                    "No puedo consultar tus posiciones en este momento.",
                    "Prefiero no darte cifras que no pueda confirmar; si quieres, te comunico con tu asesor.",
                ]
                candidates = []
            elif any(
                f
                in {
                    "search_market_news",
                    "get_actinver_research",
                    "get_market_quote",
                    "get_economic_calendar",
                }
                for f in failed
            ):
                sentences.append(
                    "No pude consultar el contexto de mercado ahora mismo, así que te respondo sólo con la información de tu portafolio."
                )

        if rewrite_hint:
            sentences = _drop_offending(sentences, rewrite_hint)
        limit = 3 if state.get("channel") == "voice" else 6
        speech = (
            " ".join(sentences[:limit]).strip()
            or "Te comunico con tu asesor para revisarlo juntos."
        )
        provider = "stub" if model.startswith(("stub", "rules")) else "fallback"
        return GenerationResult(
            speech=speech,
            candidate_product_ids=candidates,
            proposed_amount=(
                proposed.decimal
                if (proposed := state.get("proposed_amount")) is not None
                else extract_amount(state.get("client_input_text", ""))
            ),
            model=model,
            provider=provider,
            input_tokens=len(system_prompt) // 4,
            output_tokens=min(max_tokens, len(speech) // 4),
            ttft_ms=0,
        )

    @staticmethod
    def _inspect(results: dict[str, Any], name: str) -> list[str]:
        out: list[str] = []
        positions = results.get("get_portfolio_positions")
        performance = results.get("get_portfolio_performance")
        cash = results.get("get_cash_balance")
        greeting = f"{name}, " if name else ""
        if positions:
            total = positions["total_market_value"]
            out.append(
                f"{greeting}tu portafolio vale {speech_safe_amount(total['amount'], total['currency'])}."
            )
            sleeves = sorted(positions["positions"], key=lambda p: p["weight_pct"], reverse=True)
            if sleeves:
                top = sleeves[0]
                out.append(
                    f"La mayor parte está en {top['name'].lower()}, y el detalle de cada posición lo tienes en pantalla."
                )
        if performance:
            out.append(
                f"En el periodo va {direction_word(performance['period_return_pct'])}, "
                f"cerca de {speech_safe_percent(performance['period_return_pct'])}."
            )
        if cash:
            out.append(
                f"Tienes disponible {speech_safe_amount(cash['available']['amount'], cash['available']['currency'])}."
            )
        return out or ["No encontré información de tu portafolio en este momento."]

    @staticmethod
    def _explain(results: dict[str, Any]) -> list[str]:
        out: list[str] = []
        performance = results.get("get_portfolio_performance")
        attribution = results.get("get_portfolio_attribution")
        news = results.get("search_market_news") or results.get("get_actinver_research")
        if performance:
            out.append(
                f"Tu portafolio cerró el periodo {direction_word(performance['period_return_pct'])}."
            )
        if attribution and attribution["contributions"]:
            contributions = sorted(
                attribution["contributions"], key=lambda c: abs(c["bps"]), reverse=True
            )
            best = contributions[0]
            verb = "aportó" if best["bps"] >= 0 else "restó"
            out.append(
                f"Casi todo el movimiento vino de la parte de {best['sleeve'].lower()}, que {verb} más."
            )
            drags = [c for c in contributions if c["bps"] < 0 and c is not best]
            if drags:
                out.append(f"La porción de {drags[0]['sleeve'].lower()} restó un poco.")
        if news and news.get("items"):
            item = news["items"][0]
            out.append(
                f'Esto coincide con la noticia "{item["title"]}" publicada por {item["source"]}; te dejo la fuente y el desglose en pantalla.'
            )
        else:
            out.append("Te dejo el desglose en pantalla.")
        return out or ["No encontré el detalle del movimiento en este momento."]

    @staticmethod
    def _market(results: dict[str, Any]) -> list[str]:
        out: list[str] = []
        news = results.get("search_market_news")
        quotes = results.get("get_market_quote")
        if news and news.get("items"):
            item = news["items"][0]
            out.append(f"Lo más relevante: {item['title'].rstrip('.')}, según {item['source']}.")
            if len(news["items"]) > 1:
                out.append(f'También destaca "{news["items"][1]["title"]}".')
        if quotes and quotes.get("quotes"):
            quote = quotes["quotes"][0]
            delay = " con retraso" if quote["delayed"] else ""
            out.append(
                f"La cotización de {quote['symbol']}{delay} va {direction_word(quote['change_pct'])} en el día; el dato exacto está en pantalla."
            )
        out.append(
            "Esta información es de carácter general y no constituye una recomendación personalizada."
        )
        return out

    @staticmethod
    def _products(
        results: dict[str, Any],
        intent: Intent,
        degraded: bool,
        state: AdvisorState,
    ) -> tuple[list[str], list[str]]:
        out: list[str] = []
        search = results.get("search_investment_products")
        items = (search or {}).get("items", [])
        candidates = [i["product_id"] for i in items][:4]
        if not items:
            return [
                "No encontré productos con esas características; tu asesor puede revisar otras alternativas contigo."
            ], []
        names = ", ".join(i["name"] for i in items[:3])
        if intent is Intent.ADVISORY_RECOMMEND and not degraded:
            amount = state.get("proposed_amount")
            amount_text = (
                f" para {speech_safe_amount(amount.amount, amount.currency)}"
                if amount is not None
                else ""
            )
            profile = state.get("investor_profile")
            band = (
                f"con tu perfil {profile.risk_category} y horizonte de {profile.horizon_band}"
                if profile
                else "con tu perfil"
            )
            out.append(f"Revisé opciones{amount_text} {band}.")
            out.append(
                f"Las que resultaron congruentes con tu perfil las tienes en pantalla, por ejemplo {names}."
            )
            # Mandatory disclosures are injected verbatim by compliance_guard, not by the model.
        else:
            out.append(f"Te muestro algunas opciones de forma general: {names}.")
            out.append(
                "Esta información es de carácter general y no constituye una recomendación personalizada."
            )
            if degraded:
                out.append(
                    "Para una recomendación adaptada a tu situación, te comunico con tu asesor."
                )
        return out, candidates

    @staticmethod
    def _simulate(results: dict[str, Any]) -> list[str]:
        sim = results.get("simulate_investment")
        if not sim:
            return ["No pude correr la simulación en este momento."]
        base = sim["scenarios"]["base"]
        years = sim["horizon_months"] // 12
        horizon = f"{years} años" if years >= 1 else f"{sim['horizon_months']} meses"
        return [
            f"En el escenario base, en {horizon} tu inversión rondaría {speech_safe_amount(base['amount'], base['currency'])}.",
            "Los escenarios pesimista y optimista están en pantalla.",
            "Se trata de un escenario simulado con base en información histórica, no de una proyección garantizada.",
        ]

    @staticmethod
    def _transaction(results: dict[str, Any], intent: Intent) -> list[str]:
        req = results.get("get_transaction_requirements")
        if not req:
            return ["No pude preparar la operación en este momento."]
        verb = {
            Intent.TRANSACT_BUY: "la inversión",
            Intent.TRANSACT_SELL: "la venta",
            Intent.TRANSACT_SWITCH: "el cambio de fondo",
            Intent.TRANSACT_REDEEM: "el retiro",
        }[intent]
        return [
            f"Te preparé {verb} en {req['product']['name']}.",
            "Revisa el monto, la cuenta y la fecha de liquidación en pantalla; nada se ejecuta hasta que confirmes.",
        ]

    @staticmethod
    def _admin(results: dict[str, Any]) -> list[str]:
        out: list[str] = []
        if "get_account_statements" in results:
            out.append(
                "Tu estado de cuenta está listo; el enlace seguro aparece en pantalla y caduca en una hora."
            )
        if "get_transaction_history" in results:
            out.append("Te dejo tus últimos movimientos en pantalla.")
        if "get_investment_services_guide" in results:
            out.append(
                "La Guía de Servicios de Inversión vigente está en pantalla, con comisiones y el procedimiento de reclamaciones."
            )
        if "get_client_accounts" in results:
            out.append(
                "Tus cuentas elegibles aparecen en pantalla; las operaciones liquidan conforme a la fecha valor del producto."
            )
        return out or ["Te dejo la información administrativa en pantalla."]


def _drop_offending(sentences: list[str], hint: str) -> list[str]:
    """A rewrite in the stub removes the sentences that carry a figure or a
    flagged phrase; the guardrail decides whether the remainder passes."""
    from actinver_agent.guardrails import patterns as pat

    kept: list[str] = []
    for sentence in sentences:
        flagged = any(p.search(sentence) for p in pat.PROHIBITED_CLAIMS.values())
        if flagged or pat.PRECISE_AMOUNT.search(sentence) or pat.scan_identifiers(sentence):
            continue
        if "UNSOURCED_FIGURE" in hint and re.search(r"\d", sentence):
            continue
        kept.append(sentence)
    return kept or ["Te dejo el detalle en pantalla."]


class StubEmbedder:
    """Deterministic hash-based embeddings (768 dims) for local retrieval."""

    dimensions = 768

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    @classmethod
    def _embed(cls, text: str) -> list[float]:
        vector = [0.0] * cls.dimensions
        for token in re.findall(r"[a-záéíóúñ0-9]{3,}", text.lower()):
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % cls.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]


ADVISORY = ADVISORY_INTENTS  # re-exported for tests
