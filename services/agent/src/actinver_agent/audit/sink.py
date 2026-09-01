"""Evidence writer - DCGSI Art. 26 (ADR-0012).

Advisory and transactional turns are fail-closed: no evidence, no response.
Informational turns use a durable spool (Postgres) when the WORM store is
unavailable, drained later. Every record is hash-chained per thread and the
chain heads are anchored daily into a separate trust domain.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import orjson
import structlog

from actinver_agent.audit.record import canonical_hash, chain_fields, product_ids_in
from actinver_agent.ports import (
    ChainStorePort,
    EvidenceIndexRepository,
    EvidenceIndexRow,
    EvidenceWriteResult,
    ObjectStorePort,
    SpoolPort,
)

log = structlog.get_logger(__name__)


class EvidenceUnavailable(RuntimeError):
    """The evidence store is unavailable and the turn is fail-closed."""


def evidence_key(record: dict[str, Any]) -> str:
    created = datetime.fromisoformat(record["created_at"])
    return f"evidence/{created:%Y/%m}/{record['evidence_id']}.json"


class EvidenceWriter:
    def __init__(
        self,
        *,
        store: ObjectStorePort,
        chain: ChainStorePort,
        index: EvidenceIndexRepository,
        spool: SpoolPort,
        lock_mode: str = "GOVERNANCE",
        retention_years: int = 5,
        write_timeout_s: float = 3.0,
    ) -> None:
        self._store = store
        self._chain = chain
        self._index = index
        self._spool = spool
        self._lock_mode = lock_mode
        self._retention_years = retention_years
        self._timeout = write_timeout_s
        #: Serialises chain updates per process so two turns on one thread cannot
        #: race for the same ``prev_hash``.
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, thread_id: str) -> asyncio.Lock:
        return self._locks.setdefault(thread_id, asyncio.Lock())

    async def write(self, record: dict[str, Any], *, fail_closed: bool) -> EvidenceWriteResult:
        started = time.perf_counter()
        try:
            content_hash = await asyncio.wait_for(
                self._write_chained(record), timeout=self._timeout
            )
        except Exception as exc:
            log.error(
                "evidence.write_failed",
                evidence_id=record.get("evidence_id"),
                fail_closed=fail_closed,
                error=type(exc).__name__,
            )
            if fail_closed:
                raise EvidenceUnavailable(record.get("evidence_id", "")) from exc
            await self._spool.enqueue(record)
            return EvidenceWriteResult(
                evidence_id=record["evidence_id"], content_hash=None, spooled=True
            )
        log.info(
            "evidence.written",
            evidence_id=record["evidence_id"],
            service_type=record.get("service_type"),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        return EvidenceWriteResult(
            evidence_id=record["evidence_id"], content_hash=content_hash, spooled=False
        )

    async def _write_chained(self, record: dict[str, Any]) -> str:
        thread_id = record["thread_id"]
        async with self._lock(thread_id):
            prev_hash = await self._chain.head_hash(thread_id)
            record["chain"] = chain_fields(prev_hash)
            content_hash = canonical_hash(record)
            record["chain"]["content_hash"] = content_hash
            created = datetime.fromisoformat(record["created_at"])
            retain_until = datetime.fromisoformat(record["retention"]["expires_at"])
            key = evidence_key(record)
            await self._store.put_immutable(
                key,
                orjson.dumps(record),
                retain_until=retain_until,
                content_type="application/json",
            )
            await self._chain.set_head(thread_id, content_hash, record["evidence_id"])
            await self._index.index(
                EvidenceIndexRow(
                    evidence_id=record["evidence_id"],
                    client_id=record["client_id"],
                    thread_id=thread_id,
                    turn_id=record["turn_id"],
                    created_at=created,
                    service_type=record.get("service_type", "no_asesorado"),
                    service_subtype=record.get("service_subtype", "informacion"),
                    intent=record.get("intent") or "",
                    product_ids=product_ids_in(record),
                    object_key=key,
                    content_hash=content_hash,
                    legal_hold=False,
                    refused=bool((record.get("response") or {}).get("refused", False)),
                )
            )
            return content_hash

    async def drain_spool(self, limit: int = 100) -> int:
        """Write spooled informational records. Returns how many were drained."""
        batch = await self._spool.dequeue(limit)
        drained: list[int] = []
        for spool_id, record in batch:
            record.pop("chain", None)
            try:
                await self._write_chained(record)
            except Exception as exc:
                log.warning("evidence.spool_retry_later", error=type(exc).__name__)
                continue
            drained.append(spool_id)
        if drained:
            await self._spool.ack(drained)
        return len(drained)

    async def read(self, evidence_id: str) -> dict[str, Any] | None:
        row = await self._index.get(evidence_id)
        if row is None:
            return None
        body = await self._store.get(row.object_key)
        return orjson.loads(body) if body else None

    async def verify_thread(self, thread_id: str) -> tuple[bool, int, str | None]:
        """Re-walk a thread's records. Returns (ok, count, first_divergent_id).

        Any divergence is a security incident, not a data-quality issue.
        """
        rows, _ = await self._index.query(
            client_id=None,
            thread_id=thread_id,
            since=None,
            until=None,
            service_type=None,
            product_id=None,
            refused=None,
            limit=10_000,
            cursor=None,
        )
        rows = sorted(rows, key=lambda r: (r.created_at, r.evidence_id))
        expected_prev: str | None = None
        for row in rows:
            body = await self._store.get(row.object_key)
            if body is None:
                return False, len(rows), row.evidence_id
            record = orjson.loads(body)
            chain = record.get("chain", {})
            if chain.get("prev_hash") != expected_prev:
                return False, len(rows), row.evidence_id
            if canonical_hash(record) != chain.get("content_hash"):
                return False, len(rows), row.evidence_id
            expected_prev = chain["content_hash"]
        head = await self._chain.head_hash(thread_id)
        if rows and head != expected_prev:
            return False, len(rows), rows[-1].evidence_id
        return True, len(rows), None

    async def anchor_heads(
        self, anchor_store: ObjectStorePort, *, now: datetime | None = None
    ) -> str:
        """Publish every thread's head hash to a separate trust domain (EV-03)."""
        now = now or datetime.now(UTC)
        heads = await self._chain.all_heads()
        payload = {"anchored_at": now.isoformat(), "algo": "sha256", "heads": heads}
        key = f"anchors/{now:%Y/%m/%d}/heads-{now:%H%M%S}.json"
        retain_until = now.replace(year=now.year + self._retention_years)
        await anchor_store.put_immutable(
            key,
            orjson.dumps(payload, option=orjson.OPT_SORT_KEYS),
            retain_until=retain_until,
            content_type="application/json",
        )
        log.info("evidence.anchored", threads=len(heads), key=key)
        return key

    async def set_legal_hold(self, thread_id: str, *, on: bool) -> int:
        rows, _ = await self._index.query(
            client_id=None,
            thread_id=thread_id,
            since=None,
            until=None,
            service_type=None,
            product_id=None,
            refused=None,
            limit=10_000,
            cursor=None,
        )
        for row in rows:
            await self._store.set_legal_hold(row.object_key, on=on)
        return await self._index.set_legal_hold(thread_id=thread_id, on=on)

    async def write_formspec_copy(
        self, spec: dict[str, Any], *, now: datetime | None = None
    ) -> str:
        now = now or datetime.now(UTC)
        key = f"formspecs/{now:%Y/%m}/{spec['form_id']}.json"
        await self._store.put_immutable(
            key,
            orjson.dumps(spec, option=orjson.OPT_SORT_KEYS),
            retain_until=now.replace(year=now.year + self._retention_years),
            content_type="application/json",
        )
        return key

    async def write_transcript(
        self, thread_id: str, turn_id: str, line: dict[str, Any], *, now: datetime | None = None
    ) -> str:
        """Per-turn transcript object. S3 objects are immutable, so the thread's
        JSONL is materialised as one object per turn under the thread prefix."""
        now = now or datetime.now(UTC)
        key = f"transcripts/{now:%Y/%m}/{thread_id}/{turn_id}.jsonl"
        await self._store.put_immutable(
            key,
            orjson.dumps(line) + b"\n",
            retain_until=now.replace(year=now.year + self._retention_years),
            content_type="application/x-ndjson",
        )
        return key

    async def health(self) -> bool:
        try:
            return await asyncio.wait_for(self._store.health(), timeout=self._timeout)
        except Exception:
            return False


def verify_chain(records: list[dict[str, Any]]) -> tuple[bool, str | None]:
    """Pure re-walk of an ordered list of records (used by tests and the CLI)."""
    expected_prev: str | None = None
    for record in records:
        chain = record.get("chain", {})
        if chain.get("prev_hash") != expected_prev:
            return False, record.get("evidence_id")
        if canonical_hash(record) != chain.get("content_hash"):
            return False, record.get("evidence_id")
        expected_prev = chain["content_hash"]
    return True, None


# ── CLI helpers ───────────────────────────────────────────────────────────────


def _writer_of(deps: Any) -> EvidenceWriter:
    writer = getattr(deps.audit, "writer", None)
    if writer is None:
        raise RuntimeError(
            "the audit writer runs in audit-service; run this command with SVC_AUDIT_URL=inprocess "
            "and SERVICE_ROLE=audit, or call the audit service endpoints"
        )
    return writer  # type: ignore[no-any-return]


async def anchor_heads(deps: Any) -> str:
    """Daily job: publish every thread's head hash to the anchor store (EV-03)."""
    writer = _writer_of(deps)
    anchor_store = getattr(deps, "anchor_store", None)
    if anchor_store is None:
        raise RuntimeError("no anchor store configured")
    return await writer.anchor_heads(anchor_store)


async def drain_spool(deps: Any, limit: int = 500) -> int:
    """Write spooled informational records once the store is back (RB-03)."""
    return await _writer_of(deps).drain_spool(limit)
