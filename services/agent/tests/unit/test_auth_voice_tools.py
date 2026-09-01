"""Auth primitives, voice building blocks, tool gateway, stub model, retrieval,
foundation modules (secrets, flags, errors, Money)."""

from __future__ import annotations

import time
from decimal import Decimal

import pytest

from actinver_agent import flags as flagmod
from actinver_agent.auth import devkeys
from actinver_agent.auth.dpop import DpopError, DpopVerifier, normalise_htu
from actinver_agent.auth.stepup import verify_step_up_assertion
from actinver_agent.config import Settings
from actinver_agent.errors import ERRORS, api_error
from actinver_agent.graph.state import Intent, Money, ToolResult
from actinver_agent.llm.stub import (
    IntentPlanner,
    RulesIntentClassifier,
    StubEmbedder,
    extract_amount,
)
from actinver_agent.persistence.memory import MemoryCache
from actinver_agent.retrieval.indexer import ClientDataRejected, Indexer, classify_chunk
from actinver_agent.retrieval.retriever import MemoryVectorStore, Retriever
from actinver_agent.secrets import assert_not_a_secret, looks_like_secret
from actinver_agent.tools.gateway import Breaker
from actinver_agent.tools.registry import record_provenance
from actinver_agent.voice.framing import PcmFramer, strip_wav_header
from actinver_agent.voice.segmentation import SentenceSplitter
from actinver_agent.voice.stub import StubTextToSpeech

# ── auth ──────────────────────────────────────────────────────────────────────


async def test_dpop_proof_roundtrip_and_replay() -> None:
    settings = Settings()
    cache = MemoryCache()
    verifier = DpopVerifier(settings, cache)
    private_pem, public_jwk, jkt = devkeys.generate_device_key()
    token = devkeys.mint_dev_access_token("k", "cl_1", roles=[], jkt=jkt, device_id="d", ttl_s=600)
    proof = devkeys.make_dpop_proof(
        private_pem, public_jwk, "POST", "https://api.local/v1/sessions", token
    )
    assert (
        await verifier.verify(
            proof=proof,
            method="POST",
            url="https://api.local:443/v1/sessions",
            access_token=token,
            expected_jkt=jkt,
        )
        == jkt
    )
    with pytest.raises(DpopError, match="replayed_jti"):
        await verifier.verify(
            proof=proof,
            method="POST",
            url="https://api.local/v1/sessions",
            access_token=token,
            expected_jkt=jkt,
        )
    other = devkeys.make_dpop_proof(
        private_pem, public_jwk, "POST", "https://api.local/v1/other", token
    )
    with pytest.raises(DpopError, match="htu_mismatch"):
        await verifier.verify(
            proof=other,
            method="POST",
            url="https://api.local/v1/sessions",
            access_token=token,
            expected_jkt=jkt,
        )
    third = devkeys.make_dpop_proof(
        private_pem, public_jwk, "POST", "https://api.local/v1/sessions", token
    )
    with pytest.raises(DpopError, match="jkt_mismatch"):
        await verifier.verify(
            proof=third,
            method="POST",
            url="https://api.local/v1/sessions",
            access_token=token,
            expected_jkt="other",
        )


def test_normalise_htu_drops_default_ports_and_query() -> None:
    assert normalise_htu("HTTPS://Api.Local:443/v1/x?y=1") == "https://api.local/v1/x"


def test_step_up_signature_verifies_only_with_the_right_key() -> None:
    private_pem, public_jwk, _ = devkeys.generate_device_key()
    other_pem, _, _ = devkeys.generate_device_key()
    challenge = "Zm9vYmFyYmF6cXV4"  # base64 nonce
    good = devkeys.sign_challenge(private_pem, challenge)
    bad = devkeys.sign_challenge(other_pem, challenge)
    assert verify_step_up_assertion(public_jwk, challenge, good)
    assert not verify_step_up_assertion(public_jwk, challenge, bad)


# ── voice ─────────────────────────────────────────────────────────────────────


def _split(text: str) -> list[str]:
    splitter = SentenceSplitter()
    out: list[str] = []
    for char in text:
        out.extend(splitter.feed(char))
    if (tail := splitter.flush()) is not None:
        out.append(tail)
    return out


def test_sentence_splitter_respects_decimals_and_abbreviations() -> None:
    assert _split("Tu portafolio subió. La deuda aportó más. ¿Te muestro?") == [
        "Tu portafolio subió.",
        "La deuda aportó más.",
        "¿Te muestro?",
    ]
    assert _split("Subió 1.5 por ciento este mes.") == ["Subió 1.5 por ciento este mes."]
    assert _split("Lo revisa el Lic. Ramírez mañana.") == ["Lo revisa el Lic. Ramírez mañana."]
    parts = _split("palabra " * 60)
    assert len(parts) > 1 and all(not p.endswith("palab") for p in parts)


def test_pcm_framer_flushes_remainder_at_sentence_end() -> None:
    framer = PcmFramer(chunk_bytes=48_000)
    chunks = framer.feed(b"\x00" * 50_000)
    assert [len(c) for c in chunks] == [48_000]
    assert len(framer.flush()) == 2_000
    assert framer.flush() in (None, b"")


def test_strip_wav_header() -> None:
    header = (
        b"RIFF"
        + (36 + 4).to_bytes(4, "little")
        + b"WAVEfmt "
        + (16).to_bytes(4, "little")
        + b"\x00" * 16
    )
    data = header + b"data" + (4).to_bytes(4, "little") + b"abcd"
    assert strip_wav_header(data) == b"abcd"
    assert strip_wav_header(b"raw") == b"raw"


async def test_stub_tts_yields_24khz_pcm() -> None:
    tts = StubTextToSpeech()
    pcm = b"".join([chunk async for chunk in tts.synthesize_stream("hola mundo cruel")])
    assert len(pcm) % 2 == 0 and len(pcm) > 0


# ── tools ─────────────────────────────────────────────────────────────────────


def test_breaker_opens_after_threshold_and_half_opens() -> None:
    breaker = Breaker(failure_threshold=2, open_for_s=10)
    now = time.monotonic()
    breaker.record(False, now)
    assert breaker.allow(now)
    breaker.record(False, now + 1)
    assert breaker.is_open and not breaker.allow(now + 2)
    assert breaker.allow(now + 11), "half-open after the cool-down"


def test_record_provenance_registers_money_strings_and_rounded_forms() -> None:
    result = ToolResult(
        name="t",
        ok=True,
        data={
            "total": {"amount": "1247318.44", "currency": "MXN"},
            "pct": 0.87,
            "note": "recorte de 25 pb",
        },
    )
    provenance: dict = {}
    record_provenance(result, provenance)
    for key in ("1.24732e+06", "1.2", "0.87", "0.9", "25"):
        assert key in provenance, key
    assert provenance["25"].tool == "t"


# ── stub model ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("¿cuánto tengo?", Intent.PORTFOLIO_INSPECT),
        ("¿por qué bajó mi fondo?", Intent.PORTFOLIO_EXPLAIN),
        ("¿qué pasó con el peso?", Intent.MARKET_CONTEXT),
        ("¿qué fondos hay?", Intent.PRODUCT_DISCOVER),
        ("¿cuál me conviene?", Intent.ADVISORY_RECOMMEND),
        ("¿dónde invierto mis 200 mil?", Intent.ADVISORY_RECOMMEND),
        ("¿cuánto crecería en 3 años?", Intent.SIMULATE),
        ("quiero comprar", Intent.TRANSACT_BUY),
        ("quiero cambiar mi perfil de riesgo", Intent.PROFILE_UPDATE),
        ("mi estado de cuenta", Intent.ACCOUNT_ADMIN),
        ("quiero hablar con alguien", Intent.ESCALATE),
        ("no estoy de acuerdo con un cargo", Intent.COMPLAINT),
        ("¿quién ganó el partido de fútbol?", Intent.OUT_OF_SCOPE),
    ],
)
async def test_router_table_from_the_architecture_doc(text: str, intent: Intent) -> None:
    result = await RulesIntentClassifier().classify(text=text, history=[], locale="es-MX")
    assert result.intent is intent, (text, result)


async def test_router_biases_to_advisory_on_profile_matched_discovery() -> None:
    result = await RulesIntentClassifier().classify(
        text="¿qué fondos hay para mí?", history=[], locale="es-MX"
    )
    assert result.intent is Intent.ADVISORY_RECOMMEND and result.profile_filtered


def test_amount_extraction() -> None:
    assert extract_amount("quiero invertir 200 mil") == Decimal("200000")
    assert extract_amount("1.5 millones") == Decimal("1500000")
    assert extract_amount("100,000 pesos") == Decimal("100000")
    assert extract_amount("nada") is None


async def test_planner_only_plans_allowed_tools(deps) -> None:
    from actinver_agent.tools.registry import INTENT_TOOL_MAP

    planner = IntentPlanner()
    for intent in (
        Intent.PORTFOLIO_EXPLAIN,
        Intent.ADVISORY_RECOMMEND,
        Intent.TRANSACT_BUY,
        Intent.MARKET_CONTEXT,
    ):
        state = {
            "intent": intent,
            "client_input_text": "quiero invertir 100 mil en ACTIGOB-BF este mes",
            "messages": [],
        }
        declarations = deps.registry.declarations_for(str(intent))
        calls = await planner.plan(state=state, declarations=declarations)  # type: ignore[arg-type]
        assert calls and all(c.name in INTENT_TOOL_MAP[str(intent)] for c in calls), (intent, calls)
        assert all("client_id" not in c.args for c in calls)


# ── retrieval (ADR-0014 / AI-08) ──────────────────────────────────────────────


async def test_indexer_rejects_client_identifiers() -> None:
    indexer = Indexer(StubEmbedder(), MemoryVectorStore())
    with pytest.raises(ClientDataRejected):
        await indexer.index_document(
            collection="research_notes",
            doc_id="x",
            title="nota",
            source="s",
            published_at=None,
            text="El cliente con RFC GODE561231GR8 tiene saldo alto",
        )
    assert not classify_chunk("Saldo de la cuenta CLABE 002010077777777771").accepted
    assert classify_chunk("Banxico recorta la tasa de referencia").accepted


async def test_retriever_finds_seeded_note() -> None:
    from actinver_agent.retrieval.seed import RESEARCH_NOTES

    store = MemoryVectorStore()
    indexer = Indexer(StubEmbedder(), store)
    for doc in RESEARCH_NOTES:
        await indexer.index_document(collection="research_notes", **doc)
    result = await Retriever(StubEmbedder(), store).search_as_tool(
        "research_notes", query="Banxico recorta la tasa de referencia", k=2
    )
    assert result["items"] and result["items"][0]["title"].startswith("Banxico")
    assert all("published_at" in item and "source" in item for item in result["items"])


# ── foundation ────────────────────────────────────────────────────────────────


def test_money_rejects_bare_numbers_and_invalid_amounts() -> None:
    assert Money.of("1000").amount == "1000"
    with pytest.raises(ValueError):
        Money(amount="abc", currency="MXN")
    with pytest.raises(ValueError):
        Money.model_validate({"amount": "10"})  # currency is mandatory


def test_secret_heuristics() -> None:
    assert looks_like_secret("AKIAIOSFODNN7EXAMPLE1234")
    assert looks_like_secret("sk-abcdefghijklmnopqrstuvwxyz0123456789")
    assert not looks_like_secret("secretsmanager://actinver/liveavatar/api-key")
    assert not looks_like_secret("gemini-2.5-flash")
    with pytest.raises(RuntimeError):
        assert_not_a_secret("X", "ghp_abcdefghijklmnopqrstuvwxyz0123456789")


async def test_flags_defaults_and_kill_switch_store() -> None:
    cache = MemoryCache()
    flags = flagmod.FeatureFlags(cache)
    assert await flags.get("advisor.kill_switch") == "off"
    await flags.set("advisor.kill_switch", "on", actor="risk")
    assert await flags.kill_switch_active()
    assert flagmod.unexpired() == [], "an expired flag fails the build"
    assert flagmod.FLAG_INDEX["advisor.kill_switch"].owner == "Risk"


def test_error_catalogue_has_documented_statuses() -> None:
    for code, status in (
        ("FORM_EXPIRED", 409),
        ("FORM_SIGNATURE_INVALID", 400),
        ("STEP_UP_REQUIRED", 401),
        ("LIMIT_EXCEEDED", 422),
        ("RATE_LIMITED", 429),
        ("SERVICE_UNAVAILABLE", 503),
    ):
        assert ERRORS[code][0] == status
    err = api_error("RATE_LIMITED", retry_after_s=5)
    assert err.status == 429 and err.retry_after_s == 5 and err.message_es
