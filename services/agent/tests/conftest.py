"""Shared fixtures: an in-process dependency graph (memory persistence, stub
model, synthetic core, stub vendor) and a FastAPI test client over it."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

TEST_ENV: dict[str, str] = {
    "ENVIRONMENT": "local",
    "CACHE_PROVIDER": "memory",
    "CHECKPOINTER_PROVIDER": "memory",
    "OBJECT_STORE_PROVIDER": "memory",
    "SECRETS_MANAGER_ENDPOINT": "",
    "LLM_PROVIDER": "stub",
    "CORE_PROVIDER": "synthetic",
    "VOICE_PROVIDER": "stub",
    "LIVEAVATAR_PROVIDER": "stub",
    "AUTH_MODE": "dev",
    "AUTH_DEV_SIGNING_KEY_REF": "env://AUTH_DEV_SIGNING_KEY",
    "AUTH_DEV_SIGNING_KEY": "local-dev-signing-key-not-a-secret-value",
    "AUTH_DEV_PASSWORD": "actinver123",
    "CLIENT_HASH_SALT_REF": "env://CLIENT_HASH_SALT",
    "CLIENT_HASH_SALT": "test-salt",
    "FORM_SPEC_SIGNING_KEY_REF": "env://FORM_SPEC_SIGNING_KEY",
    "FORM_SPEC_SIGNING_KEY": "formspec-test-key-0123456789abcdef",
    "SUITABILITY_SIGNING_KEY_REF": "env://SUITABILITY_SIGNING_KEY",
    "SUITABILITY_SIGNING_KEY": "suitability-test-key-0123456789abcdef",
    "OTLP_ENDPOINT": "",
    "LOG_LEVEL": "WARNING",
}
for _k, _v in TEST_ENV.items():
    os.environ.setdefault(_k, _v)

from actinver_agent.auth import devkeys  # noqa: E402
from actinver_agent.auth.context import RequestContext  # noqa: E402
from actinver_agent.config import Settings  # noqa: E402
from actinver_agent.deps import Dependencies  # noqa: E402
from actinver_agent.wiring import build_dependencies  # noqa: E402

DEV_KEY = os.environ["AUTH_DEV_SIGNING_KEY"]


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
async def deps(settings: Settings) -> AsyncIterator[Dependencies]:
    built = await build_dependencies(settings)
    try:
        yield built
    finally:
        await built.aclose()


@pytest.fixture
def ctx() -> RequestContext:
    return RequestContext(client_id="cl_demo_moderado", jkt=None, device_id="dev-1")


def make_ctx(client_id: str, **kw: Any) -> RequestContext:
    return RequestContext(client_id=client_id, jkt=None, device_id="dev-1", **kw)


def token_for(client_id: str, *, roles: list[str] | None = None, jkt: str | None = None) -> str:
    return devkeys.mint_dev_access_token(
        DEV_KEY, client_id, roles=roles or [], jkt=jkt, device_id="dev-1", ttl_s=600
    )


def auth_headers(client_id: str, *, roles: list[str] | None = None, **extra: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(client_id, roles=roles)}", **extra}


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    from actinver_agent.api.app import create_app

    app = create_app(build_dependencies, settings=settings)
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse an SSE body into (event, data) pairs."""
    import json

    events: list[tuple[str, dict[str, Any]]] = []
    event_name: str | None = None
    data_lines: list[str] = []
    for line in [*body.splitlines(), ""]:
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
        elif line == "" and event_name is not None:
            payload = json.loads("\n".join(data_lines)) if data_lines else {}
            events.append((event_name, payload))
            event_name, data_lines = None, []
    return events
