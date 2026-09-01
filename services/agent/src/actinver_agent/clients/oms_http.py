"""Order management system client. Used ONLY by ``transaction-service``
(ADR-0010): the agent process never holds an OMS credential and the tool
registry never exposes this client."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from actinver_agent.clients.http_base import JsonClient, mtls_context
from actinver_agent.config import Settings


class _OrderReceipt(BaseModel):
    model_config = ConfigDict(extra="allow")

    as_of: str
    order_id: str
    status: str
    settlement_date: str


class OmsHttp:
    def __init__(self, settings: Settings, *, base_url: str) -> None:
        self._client = JsonClient(
            name="oms",
            base_url=base_url,
            timeout_s=5.0,
            verify=mtls_context(
                settings.core_api_mtls_cert_path,
                settings.core_api_mtls_key_path,
                settings.core_api_ca_path,
            ),
            max_connections=8,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def place_order(
        self, *, client_id: str, order: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        # Never retried without the idempotency key; never retried at all on 4xx.
        receipt = await self._client.post_model(
            "/orders",
            _OrderReceipt,
            json={"client_id": client_id, **order},
            headers={"Idempotency-Key": idempotency_key},
            retry=False,
        )
        return receipt.model_dump()

    async def health(self) -> bool:
        return await self._client.health()
