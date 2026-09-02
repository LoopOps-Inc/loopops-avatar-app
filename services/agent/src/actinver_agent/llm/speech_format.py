"""Speech-safe number rendering (ADR-0006, ADR-0013).

The exact figure never appears in speech; it goes to ``ui_payload``. Spoken
amounts are rounded to two significant figures and rendered the way a person
would say them aloud, in Mexican convention.
"""

from __future__ import annotations

import re
from decimal import Decimal

from actinver_agent.graph.state import normalise_figure
from actinver_agent.tools.registry import derived_keys

_UNITS = {"MXN": "pesos", "USD": "dólares", "EUR": "euros"}


def speech_safe_amount(value: Decimal | float | str, currency: str = "MXN") -> str:
    """1_247_318.44 → "alrededor de 1.2 millones de pesos"; 18_450 → "alrededor de 18 mil pesos"."""
    amount = float(Decimal(str(value)))
    unit = _UNITS.get(currency, "pesos")
    magnitude = abs(amount)
    sign = "menos " if amount < 0 else ""

    if magnitude >= 1_000_000:
        scaled = round(magnitude / 1_000_000, 1)
        word = "millón" if scaled == 1 else "millones"
        return f"alrededor de {sign}{scaled:g} {word} de {unit}"
    if magnitude >= 1_000:
        scaled = round(magnitude / 1_000, 0 if magnitude >= 10_000 else 1)
        return f"alrededor de {sign}{scaled:g} mil {unit}"
    if magnitude >= 100:
        return f"alrededor de {sign}{round(magnitude, -1):g} {unit}"
    return f"alrededor de {sign}{round(magnitude):g} {unit}"


def speech_safe_percent(value: float) -> str:
    rounded = round(float(value), 1)
    text = f"{abs(rounded):g}".replace(".", " punto ")
    sign = "menos " if rounded < 0 else ""
    return f"{sign}{text} por ciento"


def direction_word(value: float) -> str:
    if value > 0.05:
        return "al alza"
    if value < -0.05:
        return "a la baja"
    return "prácticamente sin cambio"


# ── Sanitiser for model-generated speech (ADR-0006 / ADR-0013) ────────────────

_SPEECH_FIGURE = re.compile(r"-?\d+(?:[.,]\d+)*")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")
_DECIMAL_COMMA = re.compile(r"\d+,\d+")
_YEAR = re.compile(r"(?:19|20)\d{2}")
_EXEMPT_TAIL = re.compile(
    r"\s*(?:a[nñ]os?|meses?|d[ií]as?|horas?|minutos?|semanas?|trimestres?"
    r"|opciones?|fondos?|productos?|alternativas?|pasos?|frases?)\b",
    re.IGNORECASE,
)
_UNSPOKEN_FALLBACK_ES = "Te dejo el detalle en pantalla."
_DOUBLED_APPROX = re.compile(
    r"\b(?:alrededor de|aproximadamente|cerca de|casi)\s+alrededor de\b", re.IGNORECASE
)


def _candidate_values(raw: str) -> list[float]:
    """Interpret a spoken figure token the ways es-MX text allows, most likely
    first: comma-grouped thousands, then decimal comma, then plain/decimal point."""
    body = raw.removeprefix("-")
    out: list[float] = []

    def add(value: float) -> None:
        if value not in out:
            out.append(value)

    if _THOUSANDS.fullmatch(body):
        try:
            add(float(body.replace(",", "")))
        except ValueError:
            pass
    if _DECIMAL_COMMA.fullmatch(body):
        try:
            add(float(body.replace(",", ".")))
        except ValueError:
            pass
    try:
        add(float(body))
    except ValueError:
        pass
    return out


def _rounded_spoken(value: float, provenance_keys: set[str]) -> str | None:
    """Render ``value`` as a spoken approximation whose figure exists in the
    provenance map, mirroring the ladder ``derived_keys`` registers."""
    magnitude = abs(value)
    sign = "menos " if value < 0 else ""
    prefix = "alrededor de " if magnitude >= 10 else ""
    if magnitude >= 1_000_000:
        for scaled in (round(value / 1_000_000, 1), round(value / 1_000_000, 2)):
            if normalise_figure(scaled) in provenance_keys:
                word = "millón" if scaled == 1 else "millones"
                return f"{prefix}{sign}{scaled:g} {word}"
    elif magnitude >= 1_000:
        for scaled in (round(value / 1_000, 1), round(value / 1_000, 0)):
            if normalise_figure(scaled) in provenance_keys:
                return f"{prefix}{sign}{scaled:g} mil"
    else:
        for rounded in (round(value, 1), round(value, 0)):
            if normalise_figure(rounded) in provenance_keys:
                return f"{prefix}{sign}{rounded:g}"
    return None


def _spoken_for(raw: str, provenance_keys: set[str]) -> str | None:
    negative = raw.startswith("-")
    for value in _candidate_values(raw):
        spoken = -value if negative else value
        if not set(derived_keys(spoken)) & provenance_keys:
            continue
        rendered = _rounded_spoken(spoken, provenance_keys)
        if rendered is not None:
            return rendered
    return None


def _rewrite_sentence(sentence: str, provenance_keys: set[str]) -> str | None:
    parts: list[str] = []
    cursor = 0
    for match in _SPEECH_FIGURE.finditer(sentence):
        raw = match.group(0)
        body = raw.removeprefix("-")
        if _YEAR.fullmatch(body) or _EXEMPT_TAIL.match(sentence, match.end()):
            replacement: str | None = raw
        else:
            replacement = _spoken_for(raw, provenance_keys)
        if replacement is None:
            return None
        parts.append(sentence[cursor : match.start()])
        parts.append(replacement)
        cursor = match.end()
    parts.append(sentence[cursor:])
    return "".join(parts)


def sanitize_generated_speech(speech: str, provenance_keys: set[str]) -> str:
    """Deterministic split-channel enforcement before the egress guardrail.

    The model proposes narrative; this pass guarantees every spoken figure is a
    rounded rendering that traces to the provenance map, and drops sentences
    whose figures cannot be traced. The guardrail stays the fail-closed
    authority: anything this pass misses is still blocked downstream.
    """
    kept = [
        rewritten
        for sentence in _SENTENCE_SPLIT.split(speech)
        if (rewritten := _rewrite_sentence(sentence, provenance_keys)) is not None
    ]
    return _DOUBLED_APPROX.sub("alrededor de", " ".join(kept)).strip() or _UNSPOKEN_FALLBACK_ES
