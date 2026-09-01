"""Infrastructure seams: secret resolution, memory repositories, checkpointer,
observability helpers, RFC 9457 rendering, CLI schema export, retention on memory."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import Request

from actinver_agent.config import Settings
from actinver_agent.errors import api_error, problem_response
from actinver_agent.graph.checkpointer import make_checkpointer, make_serializer
from actinver_agent.graph.state import ConsentRecord, ConsentType, Money
from actinver_agent.observability.setup import client_hash, set_client_hash_salt, span_attributes
from actinver_agent.persistence.memory import (
    MemoryConsentRepository,
    MemoryEvidenceIndexRepository,
    MemoryIdempotencyRepository,
    MemorySecrets,
    MemoryThreadRepository,
)
from actinver_agent.ports import EvidenceIndexRow, TurnRecord
from actinver_agent.secrets import SecretResolutionError, SecretResolver, assert_reference_fields


async def test_secret_resolver_schemes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings()
    (tmp_path / "formspec").write_text("from-file\n")
    monkeypatch.setenv("SOME_LOCAL_SECRET", "from-env")
    resolver = SecretResolver(
        settings=settings, manager=MemorySecrets({"actinver/x": "from-manager"}), file_root=tmp_path
    )
    assert await resolver.resolve("secretsmanager://actinver/x") == "from-manager"
    assert await resolver.resolve("kms://actinver/x") == "from-manager"
    assert await resolver.resolve("file://formspec") == "from-file"
    assert await resolver.resolve("env://SOME_LOCAL_SECRET") == "from-env"
    assert await resolver.resolve_bytes("env://SOME_LOCAL_SECRET") == b"from-env"
    assert await resolver.try_resolve("secretsmanager://missing") is None
    with pytest.raises(SecretResolutionError):
        await resolver.resolve("vault://nope")
    with pytest.raises(SecretResolutionError):
        await resolver.resolve("")


async def test_env_references_are_local_only() -> None:
    settings = Settings(environment="dev", auth={"mode": "oidc", "dpop_required": True})  # type: ignore[arg-type]
    resolver = SecretResolver(settings=settings, manager=None)
    with pytest.raises(SecretResolutionError, match="local-only"):
        await resolver.resolve("env://X")


def test_reference_fields_assertion_catches_pasted_secrets() -> None:
    settings = Settings()
    assert_reference_fields(settings)
    bad = settings.model_copy(update={"form_spec_signing_key_ref": "AKIAIOSFODNN7EXAMPLE1234"})
    with pytest.raises(RuntimeError):
        assert_reference_fields(bad)


def test_posture_validation_refuses_local_only_bindings() -> None:
    settings = Settings(environment="prod")  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="posture"):
        settings.validate_posture()


async def test_memory_thread_repository_pagination() -> None:
    repo = MemoryThreadRepository()
    thread = await repo.get_or_create(client_id="cl_1", channel="chat")
    again = await repo.get_or_create(client_id="cl_1", channel="chat")
    assert thread.thread_id == again.thread_id, "one thread per client per channel"
    now = datetime.now(UTC)
    for i in range(5):
        await repo.append_turn(
            TurnRecord(
                turn_id=f"tn_{i}",
                thread_id=thread.thread_id,
                created_at=now + timedelta(seconds=i),
                channel="chat",
                client_text=f"m{i}",
                speech="s",
                ui_payload=[],
                evidence_id=None,
                service_type="no_asesorado",
                intent="portfolio_inspect",
                error_code=None,
            )
        )
    page, cursor = await repo.list_turns(thread_id=thread.thread_id, cursor=None, limit=2)
    assert [t.turn_id for t in page] == ["tn_0", "tn_1"] and cursor
    page2, cursor2 = await repo.list_turns(thread_id=thread.thread_id, cursor=cursor, limit=2)
    assert [t.turn_id for t in page2] == ["tn_2", "tn_3"]
    page3, cursor3 = await repo.list_turns(thread_id=thread.thread_id, cursor=cursor2, limit=2)
    assert [t.turn_id for t in page3] == ["tn_4"] and cursor3 is None
    await repo.set_frozen(thread.thread_id, frozen=True)
    assert (await repo.get(thread.thread_id)).frozen  # type: ignore[union-attr]
    assert (await repo.list_for_client("cl_1"))[0].turn_count == 5


async def test_memory_consents_and_idempotency() -> None:
    consents = MemoryConsentRepository()
    now = datetime.now(UTC)
    await consents.record(
        ConsentRecord(
            client_id="cl",
            type=ConsentType.VOICE_RECORDING,
            version="v1",
            granted=True,
            granted_at=now,
        )
    )
    assert await consents.has_active(client_id="cl", type=ConsentType.VOICE_RECORDING, version="v1")
    assert not await consents.has_active(
        client_id="cl", type=ConsentType.VOICE_RECORDING, version="v2"
    )
    assert await consents.revoke(client_id="cl", type=ConsentType.VOICE_RECORDING, at=now)
    assert not await consents.has_active(
        client_id="cl", type=ConsentType.VOICE_RECORDING, version="v1"
    )

    idem = MemoryIdempotencyRepository()
    await idem.put("k", request_hash="h", response={"ok": True}, ttl_s=60)
    assert await idem.get("k") == ("h", {"ok": True})
    assert await idem.get("missing") is None


async def test_evidence_index_query_filters() -> None:
    index = MemoryEvidenceIndexRepository()
    now = datetime.now(UTC)
    for i, service in enumerate(("asesorado", "no_asesorado", "asesorado")):
        await index.index(
            EvidenceIndexRow(
                evidence_id=f"ev_{i}",
                client_id="cl",
                thread_id="th",
                turn_id=f"tn_{i}",
                created_at=now + timedelta(seconds=i),
                service_type=service,
                service_subtype="x",
                intent="advisory_recommend",
                product_ids=["ACTIGOB-BF"] if i == 0 else [],
                object_key=f"evidence/{i}.json",
                content_hash="h",
                legal_hold=False,
                refused=i == 2,
            )
        )
    rows, _ = await index.query(
        client_id="cl",
        thread_id=None,
        since=None,
        until=None,
        service_type="asesorado",
        product_id=None,
        refused=None,
        limit=10,
        cursor=None,
    )
    assert {r.evidence_id for r in rows} == {"ev_0", "ev_2"}
    rows, _ = await index.query(
        client_id=None,
        thread_id=None,
        since=None,
        until=None,
        service_type=None,
        product_id="ACTIGOB-BF",
        refused=None,
        limit=10,
        cursor=None,
    )
    assert [r.evidence_id for r in rows] == ["ev_0"]
    rows, _ = await index.query(
        client_id=None,
        thread_id=None,
        since=None,
        until=None,
        service_type=None,
        product_id=None,
        refused=True,
        limit=10,
        cursor=None,
    )
    assert [r.evidence_id for r in rows] == ["ev_2"]
    counts = await index.counts(since=now - timedelta(days=1), until=now + timedelta(days=1))
    assert counts


async def test_memory_checkpointer_and_serializer() -> None:
    saver, closer = await make_checkpointer(Settings())
    assert saver is not None and closer is None
    serde = make_serializer()
    kind, blob = serde.dumps_typed({"m": Money.of("10")})
    assert serde.loads_typed((kind, blob))["m"] == Money.of("10")


def test_observability_helpers() -> None:
    set_client_hash_salt(b"salt-a")
    first = client_hash("cl_1")
    set_client_hash_salt(b"salt-b")
    assert client_hash("cl_1") != first, "salted"
    attrs = span_attributes(
        {
            "intent": "x",
            "speech": "secret text",
            "client_id": "cl",
            "n": 3,
            "items": ["a", "b"],
            "none": None,
        }
    )
    assert attrs == {"intent": "x", "n": 3, "items": ["a", "b"]}


def test_problem_response_shape() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/x",
        "headers": [],
        "query_string": b"",
        "server": ("t", 80),
        "scheme": "http",
    }
    request = Request(scope)
    response = problem_response(request, api_error("RATE_LIMITED", retry_after_s=7))
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert response.media_type == "application/problem+json"


def test_openapi_export_for_every_role(tmp_path: Path) -> None:
    from actinver_agent.cli import _openapi_app_for

    settings = Settings()
    for role in ("suitability", "guardrail", "audit", "transaction"):
        schema = _openapi_app_for(role, settings).openapi()
        assert schema["paths"], role
