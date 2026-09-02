"""Pure helpers of the Gemini adapter (no SDK calls)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import types

from actinver_agent.adapters.gemini import (
    GeminiClassifier,
    GeminiSpeechToText,
    _schema,
    _thinking_config,
    extract_audio_pcm,
)
from actinver_agent.config import Settings


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
    fast = _thinking_config("gemini-2.5-flash", types.ThinkingLevel.MINIMAL)
    assert fast is not None
    assert fast.thinking_budget == 0
    assert fast.thinking_level is None
    assert _thinking_config("gemini-2.5-pro", types.ThinkingLevel.MINIMAL) is None


def test_gemini_3_uses_thinking_level_because_the_budget_is_deprecated() -> None:
    """Gemini 3.x rejects the numeric budget and cannot disable reasoning; depth
    is expressed with ``thinking_level`` and mixing both is a 400."""
    for model in ("gemini-3.7-flash", "gemini-3-flash", "gemini-3.1-pro-preview"):
        config = _thinking_config(model, types.ThinkingLevel.MINIMAL)

        assert config is not None, model
        assert config.thinking_level is types.ThinkingLevel.MINIMAL, model
        assert config.thinking_budget is None, model


def test_gemini_3_honours_the_requested_thinking_level() -> None:
    config = _thinking_config("gemini-3.7-flash", types.ThinkingLevel.LOW)

    assert config is not None
    assert config.thinking_level is types.ThinkingLevel.LOW


def test_extract_audio_pcm_reads_inline_data() -> None:
    part = SimpleNamespace(inline_data=SimpleNamespace(data=b"\x01\x00\x02\x00"))
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])
    assert extract_audio_pcm(response) == b"\x01\x00\x02\x00"


def test_extract_audio_pcm_returns_empty_without_audio() -> None:
    assert extract_audio_pcm(SimpleNamespace(candidates=[])) == b""
    part = SimpleNamespace(inline_data=None)
    response = SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])
    assert extract_audio_pcm(response) == b""


class _CapturingFactory:
    """Records the config the adapter builds without reaching the network."""

    def __init__(self) -> None:
        self.config: object = None

    def client(self) -> SimpleNamespace:
        async def generate_content(*, model: str, contents: str, config: object) -> object:
            self.config = config
            return SimpleNamespace(
                text='{"intent": "portfolio_inspect", "confidence": 0.9}',
                usage_metadata=None,
            )

        return SimpleNamespace(
            aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
        )


def test_router_asks_for_a_thinking_level_the_model_accepts() -> None:
    """Regression: MINIMAL is rejected by gemini-3.7-flash with 400
    INVALID_ARGUMENT, which silently degraded every turn to the fallback
    router and answered ``out_of_scope``."""
    import asyncio

    settings = Settings()
    settings.vertex.model_fast = "gemini-3.7-flash"
    factory = _CapturingFactory()
    classifier = GeminiClassifier(factory, settings, "router prompt")

    asyncio.run(classifier.classify(text="que inversiones tengo?", history=[], locale="es-MX"))

    level = factory.config.thinking_config.thinking_level
    assert level is not types.ThinkingLevel.MINIMAL
    assert level is types.ThinkingLevel(settings.vertex.thinking_level_structured)


def _stt_settings() -> Any:
    voice = SimpleNamespace(stt_language="es-MX", gemini_stt_model="gemini-2.5-flash-lite")
    return SimpleNamespace(voice=voice, vertex=SimpleNamespace(timeout_s=10.0))


async def _frames(*chunks: bytes):
    for chunk in chunks:
        yield chunk


def _factory(calls: list[Any], responses: Any) -> Any:
    if not isinstance(responses, list):
        responses = [responses]

    async def generate_content(**kwargs: Any) -> Any:
        calls.append(kwargs)
        result = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(result, Exception):
            raise result
        return result

    models = SimpleNamespace(generate_content=generate_content)
    aio = SimpleNamespace(models=models)
    client = SimpleNamespace(aio=aio)
    return SimpleNamespace(client=lambda: client)


def _response(text: str) -> Any:
    return SimpleNamespace(text=text)


async def test_stt_yields_one_final_transcript_for_an_utterance() -> None:
    calls: list[Any] = []
    audio = b"\x1a\x45\xdf\xa3" + b"x" * 4096
    factory = _factory(calls, [_response("¿Cómo va mi portafolio?")])
    adapter = GeminiSpeechToText(factory, _stt_settings())

    transcripts = [t async for t in adapter.stream(_frames(audio[:8], audio[8:]))]

    assert len(transcripts) == 1
    assert transcripts[0].text == "¿Cómo va mi portafolio?"
    assert transcripts[0].is_final is True
    assert transcripts[0].language == "es-MX"
    assert len(calls) == 1
    contents = calls[0]["contents"]
    assert contents[0].inline_data.mime_type == "audio/webm"
    assert contents[0].inline_data.data == audio


async def test_stt_skips_the_api_for_header_only_audio() -> None:
    calls: list[Any] = []
    factory = _factory(calls, [_response("texto")])
    adapter = GeminiSpeechToText(factory, _stt_settings())

    transcripts = [t async for t in adapter.stream(_frames(b"\x1a\x45\xdf\xa3" + b"x" * 100))]

    assert transcripts == []
    assert calls == []


async def test_stt_yields_nothing_when_speech_is_absent() -> None:
    calls: list[Any] = []
    factory = _factory(calls, [_response("  ")])
    adapter = GeminiSpeechToText(factory, _stt_settings())

    transcripts = [t async for t in adapter.stream(_frames(b"RIFF" + b"x" * 4096))]

    assert transcripts == []
    assert calls[0]["contents"][0].inline_data.mime_type == "audio/wav"


async def test_stt_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_seconds: float) -> None:
        return

    monkeypatch.setattr("actinver_agent.adapters.gemini.asyncio.sleep", no_sleep)
    calls: list[Any] = []
    factory = _factory(calls, [RuntimeError("503"), RuntimeError("503"), _response("hola")])
    adapter = GeminiSpeechToText(factory, _stt_settings())

    transcripts = [t async for t in adapter.stream(_frames(b"x" * 4096))]

    assert [t.text for t in transcripts] == ["hola"]
    assert len(calls) == 3


async def test_stt_raises_after_exhausted_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_seconds: float) -> None:
        return

    monkeypatch.setattr("actinver_agent.adapters.gemini.asyncio.sleep", no_sleep)
    calls: list[Any] = []
    factory = _factory(calls, RuntimeError("unavailable"))
    adapter = GeminiSpeechToText(factory, _stt_settings())

    with pytest.raises(RuntimeError):
        async for _ in adapter.stream(_frames(b"x" * 4096)):
            pass
    assert len(calls) == 3
