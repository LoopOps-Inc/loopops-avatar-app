"""Voice path over the audio WebSocket (docs/04-backend/04 §2 WS contract) and the
avatar broker lifecycle, against the emulated vendor."""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from actinver_agent.api.disclosure_docs import current_version
from actinver_agent.config import Settings
from actinver_agent.deps import Dependencies
from actinver_agent.errors import ApiError
from actinver_agent.graph.state import FIRST_TURN_CONSENTS, ConsentType
from tests.api.test_api import create_session
from tests.conftest import auth_headers, make_ctx, token_for

CLIENT = "cl_demo_moderado"


def _ack_all(client: TestClient, settings: Settings, client_id: str = CLIENT) -> None:
    for consent in (*FIRST_TURN_CONSENTS, ConsentType.VOICE_RECORDING):
        response = client.post(
            "/v1/consents",
            json={"type": consent.value, "version": current_version(settings, consent)},
            headers={**auth_headers(client_id), "Idempotency-Key": uuid.uuid4().hex},
        )
        assert response.status_code in (200, 201), response.text


def _start_avatar(client: TestClient, thread_id: str) -> dict[str, Any]:
    response = client.post(
        "/v1/avatar/session",
        json={"thread_id": thread_id},
        headers={**auth_headers(CLIENT), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _collect(ws: Any, until: str, limit: int = 60) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for _ in range(limit):
        message = json.loads(ws.receive_text())
        messages.append(message)
        if message.get("type") == until:
            break
    return messages


def test_voice_turn_over_websocket(client: TestClient, settings: Settings) -> None:
    _ack_all(client, settings)
    session = create_session(client)
    avatar = _start_avatar(client, session["thread_id"])
    token = token_for(CLIENT)

    with client.websocket_connect(f"{avatar['audio_ws_path']}?access_token={token}") as ws:
        ws.send_text(json.dumps({"type": "audio_start", "mime": "audio/webm;codecs=opus"}))
        ws.send_bytes(b"\x00" * 640)
        ws.send_text(
            json.dumps(
                {"type": "dev.transcript", "text": "¿Cómo va mi portafolio?", "confidence": 0.95}
            )
        )
        ws.send_text(json.dumps({"type": "utterance_end"}))
        messages = _collect(ws, until="turn.complete")

    types = [m["type"] for m in messages]
    assert "transcript.final" in types
    assert "agent.thinking" in types
    assert "caption" in types, "captions are mandatory (accessibility)"
    assert "ui" in types
    assert types[-1] == "turn.complete"
    complete = messages[-1]
    assert complete["evidence_id"] and complete["turn_id"]
    for message in messages:
        assert "livekit_agent_token" not in json.dumps(message)


def test_client_speak_is_accepted(client: TestClient, settings: Settings) -> None:
    _ack_all(client, settings)
    session = create_session(client)
    avatar = _start_avatar(client, session["thread_id"])
    token = token_for(CLIENT)

    with client.websocket_connect(f"{avatar['audio_ws_path']}?access_token={token}") as ws:
        ws.send_text(json.dumps({"type": "client.ready", "has_video": True, "has_audio": True}))
        greeting = json.loads(ws.receive_text())
        assert greeting["type"] == "caption"
        ws.send_text(json.dumps({"type": "client.speak", "text": "Tu portafolio va bien."}))
        ws.send_text(json.dumps({"type": "client.foreground"}))


def test_greeting_waits_for_client_ready(client: TestClient, settings: Settings) -> None:
    _ack_all(client, settings)
    session = create_session(client)
    avatar = _start_avatar(client, session["thread_id"])
    token = token_for(CLIENT)

    with client.websocket_connect(f"{avatar['audio_ws_path']}?access_token={token}") as ws:
        ws.send_text(json.dumps({"type": "client.foreground"}))
        ws.send_text(json.dumps({"type": "client.ready", "has_video": True, "has_audio": True}))
        greeting = json.loads(ws.receive_text())
        assert greeting["type"] == "caption"
        assert "Tino" in greeting["text"]


def test_websocket_requires_owner(client: TestClient, settings: Settings) -> None:
    _ack_all(client, settings)
    session = create_session(client)
    avatar = _start_avatar(client, session["thread_id"])
    other = token_for("cl_demo_agresivo")
    with (
        pytest.raises(Exception),  # noqa: B017 - close code 4403 surfaces as a disconnect
        client.websocket_connect(f"{avatar['audio_ws_path']}?access_token={other}") as ws,
    ):
        ws.receive_text()


def test_websocket_unauthenticated_is_closed(client: TestClient, settings: Settings) -> None:
    _ack_all(client, settings)
    session = create_session(client)
    avatar = _start_avatar(client, session["thread_id"])
    with (
        pytest.raises(Exception),  # noqa: B017
        client.websocket_connect(avatar["audio_ws_path"]) as ws,
    ):
        ws.receive_text()


async def test_broker_capacity_budget_and_stop(deps: Dependencies) -> None:
    broker = deps.broker
    assert broker is not None
    deps.settings.avatar.max_concurrent_sessions = 1
    ctx = make_ctx(CLIENT)
    first = await broker.start(ctx, thread_id="th_1", first_name="José", consent_version="2026-08")
    assert first.avatar_session_id.startswith("as_")
    with pytest.raises(ApiError) as excinfo:
        await broker.start(ctx, thread_id="th_1", first_name="José", consent_version="2026-08")
    assert excinfo.value.code == "AVATAR_CAPACITY"
    preflight = await broker.preflight()
    assert preflight["voice_offered"] is False and preflight["reason"] == "capacity"

    stopped = await broker.stop(first.avatar_session_id, reason="user")
    assert stopped is not None and stopped.ended
    assert await broker.stop(first.avatar_session_id, reason="user") is None, "stop is idempotent"
    record = await deps.repos.avatar_sessions.get(first.avatar_session_id)
    assert record is not None and record.end_reason == "user" and record.ended_at is not None

    deps.settings.avatar.max_concurrent_sessions = 100
    second = await broker.start(ctx, thread_id="th_1", first_name="José", consent_version="2026-08")
    assert await broker.stop_all_for_client(CLIENT, reason="logout") == 1
    remaining = broker.get(second.avatar_session_id)
    assert remaining is None or remaining.ended


async def test_broker_refuses_when_flags_are_off(deps: Dependencies) -> None:
    broker = deps.broker
    assert broker is not None
    await deps.flags.set("advisor.voice_mode", "off", actor="test")
    try:
        with pytest.raises(ApiError) as excinfo:
            await broker.start(
                make_ctx(CLIENT), thread_id="th", first_name="J", consent_version="v"
            )
        assert excinfo.value.code == "VOICE_UNAVAILABLE"
        assert (await broker.preflight())["voice_offered"] is False
    finally:
        await deps.flags.set("advisor.voice_mode", "on", actor="test")


async def test_filler_bank_is_warm_and_rotates(deps: Dependencies) -> None:
    fillers = deps.broker._fillers  # type: ignore[union-attr]
    assert fillers is not None
    seen = {fillers.next_filler()[0] for _ in range(8)}
    assert len(seen) >= 4, "fillers rotate so they do not become a tic"
    text, pcm = await fillers.greeting("José")
    assert "Tino" in text and pcm
