"""Contract tests for the LiveAvatar LITE REST lifecycle against recorded
response shapes (docs/01-architecture/05 §2, §8), including the 401 case."""

from __future__ import annotations

import httpx
import pytest
import respx

from actinver_agent.clients.liveavatar import LiveAvatarError, LiveAvatarVendor
from actinver_agent.config import LiveAvatarSettings

BASE = "https://api.liveavatar.com"

TOKEN_RESPONSE = {
    "code": 100,
    "data": {"session_id": "sess_1", "session_token": "tok_1"},
    "message": "ok",
}
START_RESPONSE = {
    "code": 100,
    "data": {
        "session_id": "sess_1",
        "livekit_url": "wss://livekit.example/room",
        "livekit_client_token": "client-jwt",
        "livekit_agent_token": "agent-jwt-never-forwarded",
        "max_session_duration": 1800,
        "ws_url": "wss://api.liveavatar.com/v1/sessions/sess_1/ws?token=abc",
    },
    "message": "ok",
}


@pytest.fixture
def vendor() -> LiveAvatarVendor:
    settings = LiveAvatarSettings(
        api_key_ref="secretsmanager://x",
        avatar_id="dd73ea75-1218-4ef3-92ce-606d5f7fbc0a",
        is_sandbox=True,
    )
    return LiveAvatarVendor(settings, api_key="sandbox-key", http=httpx.AsyncClient(timeout=5.0))


@respx.mock
async def test_create_session_sends_lite_mode_and_hides_agent_token(
    vendor: LiveAvatarVendor,
) -> None:
    token_route = respx.post(f"{BASE}/v1/sessions/token").mock(
        return_value=httpx.Response(200, json=TOKEN_RESPONSE)
    )
    start_route = respx.post(f"{BASE}/v1/sessions/start").mock(
        return_value=httpx.Response(201, json=START_RESPONSE)
    )

    session = await vendor.create_session()

    sent = token_route.calls[0].request
    assert sent.headers["X-API-KEY"] == "sandbox-key"
    body = httpx.Response(200, content=sent.content).json()
    assert (
        body["mode"] == "LITE"
        and body["is_sandbox"] is True
        and body["max_session_duration"] == 1800
    )
    assert start_route.calls[0].request.headers["Authorization"] == "Bearer tok_1"

    payload = session.client_payload()
    assert payload["livekit_client_token"] == "client-jwt"
    assert "livekit_agent_token" not in payload and "session_token" not in payload
    assert session.livekit_agent_token == "agent-jwt-never-forwarded"
    assert "agent-jwt" not in repr(session), "tokens never appear in logs or reprs"


@respx.mock
async def test_401_is_not_retried_blindly(vendor: LiveAvatarVendor) -> None:
    route = respx.post(f"{BASE}/v1/sessions/token").mock(
        return_value=httpx.Response(401, json={"code": 401, "message": "invalid key"})
    )
    with pytest.raises(LiveAvatarError) as excinfo:
        await vendor.create_session()
    assert excinfo.value.status == 401
    assert route.call_count <= 2


@respx.mock
async def test_stop_and_preflight(vendor: LiveAvatarVendor) -> None:
    respx.post(f"{BASE}/v1/sessions/token").mock(
        return_value=httpx.Response(200, json=TOKEN_RESPONSE)
    )
    respx.post(f"{BASE}/v1/sessions/start").mock(
        return_value=httpx.Response(201, json=START_RESPONSE)
    )
    stop_route = respx.post(f"{BASE}/v1/sessions/stop").mock(
        return_value=httpx.Response(200, json={"code": 100})
    )
    respx.get(BASE).mock(return_value=httpx.Response(200))
    respx.head(BASE).mock(return_value=httpx.Response(200))

    session = await vendor.create_session()
    await vendor.stop_session(session)
    assert stop_route.called
    reachable, rtt = await vendor.preflight()
    assert reachable is True and (rtt is None or rtt >= 0)


@respx.mock
async def test_create_session_honours_the_vendor_duration_cap(vendor: LiveAvatarVendor) -> None:
    """Sandbox/trial accounts cap max_session_duration (observed: 60 s). The
    broker retries once with the vendor's cap instead of failing the session."""
    rejected = {
        "code": 4000,
        "data": [{"loc": ["max_session_duration"], "message": "too long"}],
        "message": "max_session_duration (1800s) exceeds the maximum allowed (60s)",
    }
    token_route = respx.post(f"{BASE}/v1/sessions/token").mock(
        side_effect=[httpx.Response(400, json=rejected), httpx.Response(200, json=TOKEN_RESPONSE)]
    )
    respx.post(f"{BASE}/v1/sessions/start").mock(
        return_value=httpx.Response(
            201,
            json={
                **START_RESPONSE,
                "data": {**START_RESPONSE["data"], "max_session_duration": "60"},
            },
        )
    )

    session = await vendor.create_session()

    assert token_route.call_count == 2
    first = httpx.Response(200, content=token_route.calls[0].request.content).json()
    second = httpx.Response(200, content=token_route.calls[1].request.content).json()
    assert first["max_session_duration"] == 1800
    assert second["max_session_duration"] == 60
    assert session.max_session_duration_s == 60


@respx.mock
async def test_other_400s_are_not_retried(vendor: LiveAvatarVendor) -> None:
    token_route = respx.post(f"{BASE}/v1/sessions/token").mock(
        return_value=httpx.Response(400, json={"code": 4000, "message": "avatar_id not found"})
    )
    with pytest.raises(LiveAvatarError) as excinfo:
        await vendor.create_session()
    assert token_route.call_count == 1
    assert excinfo.value.duration_cap_s is None
