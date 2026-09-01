"""Actinver CRM (escalations to the promotor, UNE complaints) and the CMS that
serves the Guía de Servicios de Inversión (DCGSI Art. 24)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from actinver_agent.clients.http_base import JsonClient, mtls_context
from actinver_agent.config import Settings


class _Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: str
    data: dict[str, Any]


class CrmHttp:
    def __init__(self, settings: Settings, *, base_url: str) -> None:
        self._client = JsonClient(
            name="crm",
            base_url=base_url,
            timeout_s=settings.limits.tool_timeout_s,
            verify=mtls_context(
                settings.core_api_mtls_cert_path,
                settings.core_api_mtls_key_path,
                settings.core_api_ca_path,
            ),
            max_connections=8,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_escalation(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        # A task creation is idempotent per (client, summary); the CRM dedupes on it.
        env = await self._client.post_model(
            "/cases",
            _Envelope,
            json={"client_id": client_id, **kw},
            headers={"Idempotency-Key": f"{client_id}:{hash(kw.get('summary_es', ''))}"},
        )
        return {"as_of": env.as_of, **env.data}

    async def file_complaint(self, *, client_id: str, **kw: Any) -> dict[str, Any]:
        env = await self._client.post_model(
            "/une/complaints", _Envelope, json={"client_id": client_id, **kw}
        )
        return {"as_of": env.as_of, **env.data}

    async def get_services_guide(self, *, section: str) -> dict[str, Any]:
        env = await self._client.get_model(
            "/cms/services-guide", _Envelope, params={"section": section}
        )
        return {"as_of": env.as_of, **env.data}

    async def health(self) -> bool:
        return await self._client.health()
