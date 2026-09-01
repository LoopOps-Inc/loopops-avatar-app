"""AuditPort implemented in-process over ``EvidenceWriter``."""

from __future__ import annotations

from typing import Any

from actinver_agent.audit.sink import EvidenceWriter
from actinver_agent.ports import EvidenceWriteResult


class InProcessAudit:
    def __init__(self, writer: EvidenceWriter) -> None:
        self._writer = writer

    @property
    def writer(self) -> EvidenceWriter:
        return self._writer

    async def write(self, *, record: dict[str, Any], fail_closed: bool) -> EvidenceWriteResult:
        return await self._writer.write(record, fail_closed=fail_closed)

    async def verify_thread(self, thread_id: str) -> tuple[bool, int, str | None]:
        return await self._writer.verify_thread(thread_id)

    async def health(self) -> bool:
        return await self._writer.health()
