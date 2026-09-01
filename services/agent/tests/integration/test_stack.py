"""End-to-end against the running compose stack (``docker compose up -d``).

Skipped unless ``AGENT_BASE_URL`` is set. Same flow as ``scripts/smoke.sh``:
health → dev token → session → consents → chat turn (SSE) → history →
advisory → transaction (challenge, sign, submit) → avatar session → compliance.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

pytestmark = pytest.mark.integration

BASE = os.environ.get("AGENT_BASE_URL")
CLIENT = os.environ.get("SMOKE_CLIENT", "cl_demo_moderado")

if not BASE:
    pytest.skip("AGENT_BASE_URL not set; start the stack and export it", allow_module_level=True)


def _dev_token(client: str, roles: str = "") -> dict[str, Any]:
    cmd = [sys.executable, "scripts/dev_token.py", "--client", client, "--json"]
    if roles:
        cmd += ["--roles", roles]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True).stdout  # noqa: S603
    return json.loads(out)


def _sign(challenge: str) -> str:
    cmd = [sys.executable, "scripts/dev_token.py", "--sign-challenge", challenge]
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout.strip()  # noqa: S603


def _sse(
    client: httpx.Client, thread_id: str, text: str, headers: dict[str, str]
) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    with client.stream(
        "POST",
        f"/v1/threads/{thread_id}/messages",
        json={"text": text},
        headers={**headers, "Accept": "text/event-stream", "Idempotency-Key": str(uuid.uuid4())},
        timeout=60.0,
    ) as response:
        assert response.status_code == 200, response.read()
        name: str | None = None
        for line in response.iter_lines():
            if line.startswith("event: "):
                name = line[7:].strip()
            elif line.startswith("data: ") and name:
                events.append((name, json.loads(line[6:])))
                if name == "done":
                    break
    return events


def _first(events: list[tuple[str, dict[str, Any]]], name: str) -> dict[str, Any] | None:
    return next((data for ev, data in events if ev == name), None)


@pytest.fixture(scope="module")
def http() -> Iterator[httpx.Client]:
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="module")
def auth() -> dict[str, str]:
    token = _dev_token(CLIENT)["access_token"]
    return {"Authorization": f"Bearer {token}", "Accept-Language": "es-MX"}


@pytest.fixture(scope="module")
def compliance_auth() -> dict[str, str]:
    token = _dev_token("officer_demo", "compliance,risk")["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Reason": "integration test"}


@pytest.fixture(scope="module")
def session(http: httpx.Client, auth: dict[str, str]) -> dict[str, Any]:
    response = http.post(
        "/v1/sessions",
        json={
            "channel": "chat",
            "device_id": "dev-device-1",
            "device_public_jwk": _dev_token(CLIENT)["public_jwk"],
        },
        headers={**auth, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code in (200, 201), response.text
    body = response.json()
    # First-turn consents (Art. 24 guide, privacy notice, AI disclosure), at the
    # versions the server currently requires.
    public_ids = {
        "privacy_notice": "PRIVACY_NOTICE",
        "investment_services_guide": "SERVICES_GUIDE",
        "ai_disclosure": "AI_ASSISTANT",
        "voice_recording": "VOICE_RECORDING",
    }
    for consent_type, public_id in public_ids.items():
        version = next(d["version"] for d in body["disclosures_required"] if d["id"] == public_id)
        response = http.post(
            "/v1/consents",
            json={"type": consent_type, "version": version, "granted": True},
            headers={**auth, "Idempotency-Key": f"it-consent-{consent_type}-{uuid.uuid4().hex}"},
        )
        assert response.status_code in (200, 201), response.text
    return body


def test_health(http: httpx.Client) -> None:
    assert http.get("/healthz").status_code == 200
    ready = http.get("/readyz").json()
    assert ready["ready"] is True, ready


def test_session_shape(session: dict[str, Any]) -> None:
    assert session["thread_id"]
    assert set(session["capabilities"]) == {"chat", "voice", "advisory", "transactional"}
    ids = {d["id"] for d in session["disclosures_required"]}
    assert {"SERVICES_GUIDE", "AI_ASSISTANT", "VOICE_RECORDING"} <= ids
    assert session["client"]["first_name"]


def test_chat_turn_streams_split_channel(
    http: httpx.Client, auth: dict[str, str], session: dict[str, Any]
) -> None:
    events = _sse(http, session["thread_id"], "¿Cómo va mi portafolio?", auth)
    names = [name for name, _ in events]
    assert names[-1] == "done", names
    assert "token" in names and "ui" in names
    done = _first(events, "done")
    assert done and done["turn_id"] and done["evidence_id"]
    for _, data in events:
        if "type" in data and "payload" in data:
            assert "as_of" in data or data["type"] in {
                "citations",
                "escalation_offer",
                "disclosure",
            }


def test_history(http: httpx.Client, auth: dict[str, str], session: dict[str, Any]) -> None:
    response = http.get(f"/v1/threads/{session['thread_id']}", headers=auth, params={"limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["thread_id"] == session["thread_id"]
    assert len(body["turns"]) >= 1


def test_advisory_turn_passes_suitability_gate(
    http: httpx.Client, auth: dict[str, str], session: dict[str, Any]
) -> None:
    events = _sse(
        http, session["thread_id"], "¿Dónde me conviene invertir 200 mil pesos a dos años?", auth
    )
    done = _first(events, "done")
    assert done is not None
    if session["capabilities"]["advisory"]:
        assert done["service_type"] == "asesorado"
        assert any(data.get("type") == "suitability_summary" for _, data in events)
    else:
        assert done["service_type"] == "no_asesorado"


def test_transaction_flow(
    http: httpx.Client, auth: dict[str, str], session: dict[str, Any]
) -> None:
    if not session["capabilities"]["transactional"]:
        pytest.skip("client not contracted for execution")
    events = _sse(http, session["thread_id"], "Quiero invertir 100 mil pesos en ACTIGOB-BF", auth)
    form = _first(events, "form_spec")
    assert form is not None, [n for n, _ in events]
    acks = [d["id"] for d in form["disclosures"] if d.get("ack")]

    challenge = http.post(
        "/v1/auth/step-up/challenge",
        json={"form_id": form["form_id"], "amount": {"amount": "100000.00", "currency": "MXN"}},
        headers={**auth, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert challenge.status_code in (200, 201), challenge.text
    ch = challenge.json()
    assertion = _sign(ch["challenge"])

    submit = http.post(
        f"/v1/threads/{session['thread_id']}/forms/{form['form_id']}/submit",
        json={
            "values": {
                "amount": {"amount": "100000.00", "currency": "MXN"},
                "account_id": "acc_demo_1",
                "recurring": False,
            },
            "acknowledgements": acks,
            "challenge_id": ch["challenge_id"],
            "step_up_assertion": assertion,
        },
        headers={**auth, "Idempotency-Key": f"it-{form['form_id']}"},
    )
    assert submit.status_code == 200, submit.text
    receipt = submit.json()
    assert receipt["status"] == "RECEIVED" and receipt["order_id"]

    # Single-use form: a second submission must be refused.
    again = http.post(
        f"/v1/threads/{session['thread_id']}/forms/{form['form_id']}/submit",
        json={
            "values": {
                "amount": {"amount": "100000.00", "currency": "MXN"},
                "account_id": "acc_demo_1",
                "recurring": False,
            },
            "acknowledgements": acks,
            "challenge_id": ch["challenge_id"],
            "step_up_assertion": assertion,
        },
        headers={**auth, "Idempotency-Key": f"it-{form['form_id']}"},
    )
    # Same idempotency key + same body → replay of the receipt (200) is acceptable;
    # anything else must be a typed refusal.
    assert again.status_code in (200, 401, 409), again.text


def test_avatar_session_never_leaks_agent_token(
    http: httpx.Client, auth: dict[str, str], session: dict[str, Any]
) -> None:
    preflight = http.get("/v1/avatar/preflight", headers=auth)
    assert preflight.status_code == 200
    response = http.post(
        "/v1/avatar/session",
        json={"thread_id": session["thread_id"]},
        headers={**auth, "Idempotency-Key": str(uuid.uuid4())},
    )
    if response.status_code == 503:
        pytest.skip(f"voice unavailable: {response.json().get('code')}")
    assert response.status_code in (200, 201), response.text
    body = response.json()
    assert "livekit_agent_token" not in json.dumps(body)
    assert body["livekit_client_token"] and body["avatar_session_id"]
    stop = http.post(
        "/v1/avatar/session/stop",
        json={"avatar_session_id": body["avatar_session_id"], "reason": "user"},
        headers={**auth, "Idempotency-Key": str(uuid.uuid4())},
    )
    assert stop.status_code == 200 and stop.json()["stopped"] is True


def test_config_and_telemetry(http: httpx.Client, auth: dict[str, str]) -> None:
    config = http.get("/v1/config", headers=auth).json()
    assert config["kill_switch"] is False
    tele = http.post(
        "/v1/telemetry",
        json={
            "events": [
                {
                    "name": "ui.unknown_component",
                    "attributes": {"type": "x", "client_id": "strip-me"},
                }
            ]
        },
        headers=auth,
    )
    assert tele.status_code in (200, 202, 204)


def test_compliance_evidence_and_chain(
    http: httpx.Client, compliance_auth: dict[str, str], session: dict[str, Any]
) -> None:
    listing = http.get(
        "/v1/compliance/evidence",
        params={"thread_id": session["thread_id"], "limit": 20},
        headers=compliance_auth,
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"], "one immutable record per turn (EV-01)"
    verify = http.get(
        f"/v1/compliance/evidence/verify/{session['thread_id']}",
        headers=compliance_auth,
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["ok"] is True
    summary = http.get(
        "/v1/compliance/summary",
        params={"since": "2026-01-01T00:00:00Z", "until": "2027-01-01T00:00:00Z"},
        headers=compliance_auth,
    )
    assert summary.status_code == 200


def test_kill_switch_drill(
    http: httpx.Client,
    auth: dict[str, str],
    compliance_auth: dict[str, str],
    session: dict[str, Any],
) -> None:
    flip = http.put(
        "/v1/compliance/flags/advisor.kill_switch",
        json={"value": "on", "reason": "integration drill"},
        headers=compliance_auth,
    )
    assert flip.status_code in (200, 204), flip.text
    try:
        events = _sse(http, session["thread_id"], "¿Cómo va mi portafolio?", auth)
        error = _first(events, "error")
        assert error is not None and error["code"] == "KILL_SWITCH"
        assert _first(events, "done") is not None, "done always fires, even after error"
    finally:
        http.put(
            "/v1/compliance/flags/advisor.kill_switch",
            json={"value": "off", "reason": "integration drill end"},
            headers=compliance_auth,
        )
