"""Evidence writer: hash chain, WORM retention, spool, legal hold (ADR-0012)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from actinver_agent.audit.record import build_record, canonical_hash, new_evidence_id
from actinver_agent.audit.sink import EvidenceUnavailable, EvidenceWriter, verify_chain
from actinver_agent.graph.state import AgentError, Intent
from actinver_agent.persistence.memory import (
    MemoryChainStore,
    MemoryEvidenceIndexRepository,
    MemoryObjectStore,
    MemorySpool,
    ObjectLocked,
)


def _record(
    thread_id: str = "th_1", turn: str = "tn_1", intent: Intent = Intent.PORTFOLIO_INSPECT
) -> dict:
    state = {
        "client_id": "cl_1",
        "thread_id": thread_id,
        "turn_id": turn,
        "channel": "chat",
        "intent": intent,
        "service_type": "no_asesorado",
        "client_input_text": "¿cuánto tengo?",
        "speech": "Tu portafolio va al alza.",
        "ui_payload": [],
        "citations": [],
    }
    return build_record(
        state,  # type: ignore[arg-type]
        model_meta={"model": "stub"},
        prompt_version="advisor-es-MX@2026-08-20",
        ruleset_version=14,
        disclosures_shown={"PAST_PERF": "2026-08"},
        client_input={"modality": "text", "transcript": "¿cuánto tengo?"},
    )


@pytest.fixture
def parts() -> tuple[
    MemoryObjectStore, MemoryChainStore, MemoryEvidenceIndexRepository, MemorySpool
]:
    return MemoryObjectStore(), MemoryChainStore(), MemoryEvidenceIndexRepository(), MemorySpool()


def make_writer(parts, *, store=None) -> EvidenceWriter:
    obj, chain, index, spool = parts
    return EvidenceWriter(
        store=store or obj, chain=chain, index=index, spool=spool, lock_mode="GOVERNANCE"
    )


def test_record_has_the_documented_shape() -> None:
    record = _record()
    for key in (
        "evidence_id",
        "schema_version",
        "thread_id",
        "turn_id",
        "client_id",
        "created_at",
        "channel",
        "service_type",
        "client_input",
        "tool_calls",
        "model",
        "guardrails",
        "response",
        "retention",
    ):
        assert key in record, key
    assert record["schema_version"] == "1.0"
    assert record["retention"]["class"] == "DCGSI_ART26"
    assert record["response"]["disclosures"] == {"PAST_PERF": "2026-08"}
    assert record["model"]["prompt_version"] == "advisor-es-MX@2026-08-20"
    assert new_evidence_id().startswith("ev_")


async def test_chain_links_records_per_thread(parts) -> None:
    writer = make_writer(parts)
    first = await writer.write(_record(turn="tn_1"), fail_closed=True)
    second = await writer.write(_record(turn="tn_2"), fail_closed=True)
    assert not first.spooled and not second.spooled
    ok, count, divergent = await writer.verify_thread("th_1")
    assert ok and count == 2 and divergent is None
    obj, chain, *_ = parts
    assert await chain.head_hash("th_1") == second.content_hash
    keys = await obj.list_keys("evidence/")
    assert len(keys) == 2 and all(k.endswith(".json") for k in keys)


async def test_worm_objects_cannot_be_overwritten(parts) -> None:
    writer = make_writer(parts)
    result = await writer.write(_record(), fail_closed=True)
    obj = parts[0]
    key = (await obj.list_keys("evidence/"))[0]
    with pytest.raises(ObjectLocked):
        await obj.put_immutable(
            key,
            b"tamper",
            retain_until=datetime(2031, 1, 1, tzinfo=UTC),
            content_type="application/json",
        )
    with pytest.raises(ObjectLocked):
        await obj.delete(key)
    assert result.content_hash


async def test_tampering_is_detected_by_verify_chain() -> None:
    records = [_record(turn="tn_1"), _record(turn="tn_2")]
    prev = None
    for record in records:
        record["chain"] = {"prev_hash": prev, "algo": "sha256"}
        record["chain"]["content_hash"] = canonical_hash(record)
        prev = record["chain"]["content_hash"]
    assert verify_chain(records) == (True, None)
    records[0]["response"]["speech"] = "otra cosa"
    ok, divergent = verify_chain(records)
    assert not ok and divergent == records[0]["evidence_id"]


async def test_fail_closed_raises_when_store_is_down(parts) -> None:
    writer = make_writer(parts, store=MemoryObjectStore(fail=True))
    with pytest.raises(EvidenceUnavailable):
        await writer.write(_record(intent=Intent.ADVISORY_RECOMMEND), fail_closed=True)


async def test_informational_turns_spool_when_store_is_down(parts) -> None:
    _obj, chain, index, spool = parts
    down = MemoryObjectStore(fail=True)
    writer = EvidenceWriter(
        store=down, chain=chain, index=index, spool=spool, lock_mode="GOVERNANCE"
    )
    result = await writer.write(_record(), fail_closed=False)
    assert result.spooled and await spool.depth() == 1
    down.fail = False  # store recovers
    drained = await writer.drain_spool()
    assert drained == 1 and await spool.depth() == 0
    ok, count, _ = await writer.verify_thread("th_1")
    assert ok and count == 1


async def test_legal_hold_and_anchor(parts) -> None:
    writer = make_writer(parts)
    await writer.write(_record(), fail_closed=True)
    held = await writer.set_legal_hold("th_1", on=True)
    assert held == 1
    anchor = MemoryObjectStore()
    anchored = await writer.anchor_heads(anchor)
    assert anchored
    assert await anchor.list_keys("anchors/")


def test_refusals_are_records_too() -> None:
    state = {
        "client_id": "cl_1",
        "thread_id": "th_1",
        "turn_id": "tn_9",
        "channel": "chat",
        "intent": Intent.ADVISORY_RECOMMEND,
        "service_type": "asesorado",
        "error": AgentError(code="PROFILE_EXPIRED", message_es="...", escalate=True),
        "ui_payload": [],
        "citations": [],
    }
    record = build_record(state, model_meta=None, prompt_version="p", ruleset_version=14)  # type: ignore[arg-type]
    assert record["service_type"] == "asesorado"
    assert record.get("refusal") or record.get("error")
