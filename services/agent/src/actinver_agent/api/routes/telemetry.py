"""``POST /v1/telemetry`` - client telemetry ingest.

The app strips known sensitive field names before emitting; the backend does
the same on receipt (docs/03-mobile/02 §5). Nothing here is trusted.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, Response, status

from actinver_agent.api.schemas import TelemetryBatch
from actinver_agent.auth.context import RequestContext
from actinver_agent.auth.dependencies import require_client
from actinver_agent.observability.setup import _FORBIDDEN_KEYS, client_hash

router = APIRouter(prefix="/v1", tags=["telemetry"])
log = structlog.get_logger(__name__)


def strip_sensitive(attributes: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in attributes.items():
        if key.lower() in _FORBIDDEN_KEYS:
            continue
        if isinstance(value, dict):
            clean[key] = strip_sensitive(value)
        elif isinstance(value, str):
            clean[key] = value[:200]
        elif isinstance(value, (int, float, bool)) or value is None:
            clean[key] = value
    return clean


@router.post(
    "/telemetry",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest client telemetry",
    description="Accepts up to 200 events. Known sensitive field names are dropped server-side.",
    response_class=Response,
)
async def ingest(batch: TelemetryBatch, ctx: RequestContext = Depends(require_client)) -> Response:
    for event in batch.events:
        log.info(
            "client.telemetry",
            event_name=event.name[:80],
            client_hash=client_hash(ctx.client_id),
            **strip_sensitive(event.attributes),
        )
    return Response(status_code=status.HTTP_202_ACCEPTED)
