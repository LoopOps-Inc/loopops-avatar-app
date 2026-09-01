"""Speech-safe number rendering (ADR-0006, ADR-0013).

The exact figure never appears in speech; it goes to ``ui_payload``. Spoken
amounts are rounded to two significant figures and rendered the way a person
would say them aloud, in Mexican convention.
"""

from __future__ import annotations

from decimal import Decimal

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
