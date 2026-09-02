"""Speech sanitiser tests: model-generated figures become traceable rounded
speech (ADR-0006 split-channel), and the sanitised output passes the egress
guardrail that previously hard-blocked the Gemini path."""

from __future__ import annotations

import pytest

from actinver_agent.graph.state import GuardrailAction, Intent
from actinver_agent.guardrails.disclosures import load_disclosures
from actinver_agent.guardrails.engine import GuardrailEngine
from actinver_agent.llm.speech_format import sanitize_generated_speech
from actinver_agent.ports import OutputCheckRequest
from actinver_agent.tools.registry import derived_keys


def provenance_for(*values: float) -> set[str]:
    keys: set[str] = set()
    for value in values:
        keys.update(derived_keys(value))
    return keys


@pytest.fixture(scope="module")
def engine() -> GuardrailEngine:
    return GuardrailEngine(load_disclosures("prompts"))


def output_request(speech: str, provenance_keys: set[str]) -> OutputCheckRequest:
    return OutputCheckRequest(
        speech=speech,
        intent=Intent.PORTFOLIO_INSPECT,
        locale="es-MX",
        register="tu",
        provenance_keys=frozenset(provenance_keys),
        stripped_product_terms=(),
        rewrite_attempts=0,
        max_rewrite_attempts=2,
    )


def test_grouped_thousands_figure_is_rounded_and_traceable() -> None:
    """Regression: the model spoke '4,187' (grouped digits, read by the
    guardrail as 4.187) and the turn hard-blocked."""
    keys = provenance_for(4187.50)
    speech = sanitize_generated_speech(
        "Tienes 4,187 pesos disponibles y tu portafolio va al alza.", keys
    )
    assert "4,187" not in speech
    assert "alrededor de 4.2 mil" in speech
    assert "va al alza" in speech


def test_precise_decimal_is_rounded_to_one_decimal() -> None:
    keys = provenance_for(203.55)
    speech = sanitize_generated_speech("Tu portafolio llevó 203.55 este mes.", keys)
    assert "203.55" not in speech
    assert "alrededor de 203.6" in speech


def test_millions_render_like_the_stub_templates() -> None:
    keys = provenance_for(1_247_318.44)
    speech = sanitize_generated_speech("Tu portafolio vale 1,247,318.44 pesos.", keys)
    assert "alrededor de 1.2 millones" in speech


def test_untraceable_figure_drops_only_its_sentence() -> None:
    keys = provenance_for(4187.50)
    speech = sanitize_generated_speech(
        "Tu reserva es de 999,999 pesos. El resto te lo muestro en pantalla.", keys
    )
    assert "reserva" not in speech
    assert "El resto te lo muestro en pantalla." in speech


def test_years_and_ordinal_enumerations_are_left_alone() -> None:
    keys = provenance_for(4187.50)
    speech = sanitize_generated_speech(
        "En 2024 cerraste bien y te mostré 3 opciones de fondo.", keys
    )
    assert "2024" in speech
    assert "3 opciones" in speech


def test_already_safe_speech_is_unchanged() -> None:
    keys = provenance_for(1_247_318.44, 0.87)
    original = "Tu portafolio vale alrededor de 1.2 millones y va 0.9 por ciento arriba."
    assert sanitize_generated_speech(original, keys) == original


def test_all_sentences_untraceable_falls_back_to_a_safe_line() -> None:
    assert sanitize_generated_speech("Ganaste 55,555 pesos.", set()) == (
        "Te dejo el detalle en pantalla."
    )


def test_model_qualifier_is_not_doubled() -> None:
    keys = provenance_for(184_236.96)
    speech = sanitize_generated_speech(
        "Tienes aproximadamente 184,236 pesos disponibles en efectivo.", keys
    )
    assert speech == "Tienes alrededor de 184.2 mil pesos disponibles en efectivo."


def test_sanitised_output_passes_the_egress_guardrail(engine: GuardrailEngine) -> None:
    """The bug this fixes end to end: BLOCKED_OUTPUT on portfolio answers."""
    keys = provenance_for(4187.50, 203.55)
    raw = "Tienes 4,187 pesos disponibles. Este mes movió 203.55, sin más."
    sanitised = sanitize_generated_speech(raw, keys)
    verdict = engine.check_output(output_request(sanitised, keys))
    assert verdict.action is GuardrailAction.PASS
    blocked = engine.check_output(output_request(raw, keys))
    assert blocked.action is GuardrailAction.BLOCK
