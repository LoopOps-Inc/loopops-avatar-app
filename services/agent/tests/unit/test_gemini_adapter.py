"""Pure helpers of the Gemini adapter (no SDK calls)."""

from __future__ import annotations

from types import SimpleNamespace

from actinver_agent.adapters.gemini import _schema, _thinking_config, extract_audio_pcm


def test_schema_keeps_property_names_and_strips_unsupported_keywords() -> None:
    """Regression: property names were filtered as if they were schema keywords,
    so Gemini received ``required`` entries without properties (400 INVALID_ARGUMENT)."""
    raw = {
        "additionalProperties": False,
        "properties": {
            "product_id": {
                "maxLength": 40,
                "pattern": "^[A-Z0-9-]+$",
                "title": "Product Id",
                "type": "string",
            },
            "amount": {
                "anyOf": [{"exclusiveMinimum": 0.0, "type": "number"}, {"type": "string"}],
                "description": "Monto",
                "title": "Amount",
            },
        },
        "required": ["product_id", "amount"],
        "type": "object",
    }
    cleaned = _schema(raw)
    assert set(cleaned["properties"]) == {"product_id", "amount"}
    assert cleaned["required"] == ["product_id", "amount"]
    assert cleaned["properties"]["product_id"] == {"maxLength": 40, "type": "string"}
    assert "additionalProperties" not in cleaned
    assert "title" not in cleaned["properties"]["amount"]
    for name in cleaned["required"]:
        assert name in cleaned["properties"]


def test_schema_collapses_optional_anyof_to_nullable() -> None:
    raw = {
        "properties": {"note": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
        "type": "object",
    }
    assert _schema(raw)["properties"]["note"] == {"type": "string", "nullable": True}


def test_thinking_is_disabled_only_where_the_model_allows_it() -> None:
    assert _thinking_config("gemini-2.5-flash") is not None
    assert _thinking_config("gemini-2.5-flash").thinking_budget == 0
    assert _thinking_config("gemini-2.5-pro") is None


def test_extract_audio_pcm_reads_inline_data() -> None:
    part = SimpleNamespace(inline_data=SimpleNamespace(data=b"\x01\x00\x02\x00"))
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])
    assert extract_audio_pcm(response) == b"\x01\x00\x02\x00"


def test_extract_audio_pcm_returns_empty_without_audio() -> None:
    assert extract_audio_pcm(SimpleNamespace(candidates=[])) == b""
    part = SimpleNamespace(inline_data=None)
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])
    assert extract_audio_pcm(response) == b""
