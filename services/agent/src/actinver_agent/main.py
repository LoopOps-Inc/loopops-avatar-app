"""ASGI entrypoint for the agent role: ``uvicorn actinver_agent.main:app``."""

from __future__ import annotations

from actinver_agent.api.app import create_app

app = create_app()
