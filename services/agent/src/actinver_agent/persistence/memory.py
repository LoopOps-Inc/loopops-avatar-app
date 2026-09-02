"""In-memory implementations of every port - the test doubles.

They honour the same semantics as the real adapters where it matters for
correctness: the object store refuses to overwrite or delete a locked key, the
cache implements sliding windows and slots, repositories paginate by cursor.
"""

from __future__ import annotations

import base64
import dataclasses
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from actinver_agent.graph.state import ConsentRecord, ConsentType, FormSpec
from actinver_agent.persistence.thread_id import derive_thread_id
from actinver_agent.ports import (
    AvatarSessionRecord,
    DeviceBinding,
    EvidenceIndexRow,
    ThreadRecord,
    TurnRecord,
)


class ObjectLocked(RuntimeError):
    pass


# ── Object store ───────────────────────────────────────────────────────────────


@dataclass
class _StoredObject:
    body: bytes
    content_type: str
    retain_until: datetime | None
    expires_at: datetime | None
    legal_hold: bool = False


class MemoryObjectStore:
    def __init__(self, *, fail: bool = False) -> None:
        self.objects: dict[str, _StoredObject] = {}
        self.fail = fail

    def _check_available(self) -> None:
        if self.fail:
            raise ConnectionError("object store unavailable")

    async def put_immutable(
        self, key: str, body: bytes, *, retain_until: datetime, content_type: str
    ) -> None:
        self._check_available()
        existing = self.objects.get(key)
        if existing and existing.retain_until and existing.retain_until > datetime.now(UTC):
            raise ObjectLocked(key)
        self.objects[key] = _StoredObject(body, content_type, retain_until, None)

    async def put_expiring(
        self, key: str, body: bytes, *, expires_at: datetime, content_type: str
    ) -> None:
        self._check_available()
        self.objects[key] = _StoredObject(body, content_type, None, expires_at)

    async def get(self, key: str) -> bytes | None:
        self._check_available()
        obj = self.objects.get(key)
        return obj.body if obj else None

    async def list_keys(self, prefix: str) -> list[str]:
        self._check_available()
        return sorted(k for k in self.objects if k.startswith(prefix))

    async def set_legal_hold(self, key: str, *, on: bool) -> None:
        self._check_available()
        if key in self.objects:
            self.objects[key].legal_hold = on

    async def presign_get(self, key: str, *, ttl_s: int) -> str:
        return f"memory://{key}?ttl={ttl_s}"

    async def delete(self, key: str) -> None:
        obj = self.objects.get(key)
        if obj and ((obj.retain_until and obj.retain_until > datetime.now(UTC)) or obj.legal_hold):
            raise ObjectLocked(key)
        self.objects.pop(key, None)

    async def health(self) -> bool:
        return not self.fail


# ── Cache ──────────────────────────────────────────────────────────────────────


class MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[bytes, float | None]] = {}
        self._windows: dict[str, list[float]] = defaultdict(list)
        self._slots: dict[str, dict[str, float]] = defaultdict(dict)
        self._flags: dict[str, str] = {}

    def _alive(self, key: str) -> bytes | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and expires < time.monotonic():
            del self._data[key]
            return None
        return value

    async def get(self, key: str) -> bytes | None:
        return self._alive(key)

    async def set(self, key: str, value: bytes, *, ttl_s: int | None) -> None:
        self._data[key] = (value, time.monotonic() + ttl_s if ttl_s else None)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def incr(self, key: str, *, ttl_s: int | None = None) -> int:
        current = int((self._alive(key) or b"0").decode())
        current += 1
        await self.set(key, str(current).encode(), ttl_s=ttl_s)
        return current

    async def sliding_window_hit(self, key: str, *, limit: int, window_s: int) -> bool:
        now = time.monotonic()
        hits = [t for t in self._windows[key] if t > now - window_s]
        hits.append(now)
        self._windows[key] = hits
        return len(hits) <= limit

    async def acquire_slot(self, key: str, *, limit: int, member: str, ttl_s: int) -> bool:
        now = time.monotonic()
        slots = {m: exp for m, exp in self._slots[key].items() if exp > now}
        if member not in slots and len(slots) >= limit:
            self._slots[key] = slots
            return False
        slots[member] = now + ttl_s
        self._slots[key] = slots
        return True

    async def release_slot(self, key: str, *, member: str) -> None:
        self._slots[key].pop(member, None)

    async def slot_count(self, key: str) -> int:
        now = time.monotonic()
        return sum(1 for exp in self._slots[key].values() if exp > now)

    async def get_flag(self, name: str) -> str | None:
        return self._flags.get(name)

    async def set_flag(self, name: str, value: str) -> None:
        self._flags[name] = value

    async def health(self) -> bool:
        return True


class MemorySecrets:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = dict(values or {})

    async def get(self, name: str) -> str:
        return self.values[name]

    async def put(self, name: str, value: str) -> None:
        self.values[name] = value


# ── Chain and spool ────────────────────────────────────────────────────────────


class MemoryChainStore:
    def __init__(self) -> None:
        self.heads: dict[str, tuple[str, str]] = {}

    async def head_hash(self, thread_id: str) -> str | None:
        head = self.heads.get(thread_id)
        return head[0] if head else None

    async def set_head(self, thread_id: str, content_hash: str, evidence_id: str) -> None:
        self.heads[thread_id] = (content_hash, evidence_id)

    async def all_heads(self) -> dict[str, str]:
        return {t: h for t, (h, _) in self.heads.items()}


class MemorySpool:
    def __init__(self) -> None:
        self.items: dict[int, dict[str, Any]] = {}
        self._next = 1

    async def enqueue(self, record: dict[str, Any]) -> None:
        self.items[self._next] = record
        self._next += 1

    async def dequeue(self, limit: int) -> list[tuple[int, dict[str, Any]]]:
        return sorted(self.items.items())[:limit]

    async def ack(self, ids: list[int]) -> None:
        for i in ids:
            self.items.pop(i, None)

    async def depth(self) -> int:
        return len(self.items)


# ── Repositories ───────────────────────────────────────────────────────────────


def _encode_cursor(created_at: datetime, ident: str) -> str:
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{ident}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    ts, ident = raw.split("|", 1)
    return datetime.fromisoformat(ts), ident


class MemoryThreadRepository:
    def __init__(self) -> None:
        self.threads: dict[str, ThreadRecord] = {}
        self.turns: dict[str, list[TurnRecord]] = defaultdict(list)

    async def get_or_create(self, *, client_id: str, channel: str) -> ThreadRecord:
        for t in self.threads.values():
            if t.client_id == client_id:
                return t
        thread_id = derive_thread_id(client_id, salt="memory")
        record = ThreadRecord(
            thread_id=thread_id,
            client_id=client_id,
            channel=channel,
            created_at=datetime.now(UTC),
            frozen=False,
            turn_count=0,
        )
        self.threads[thread_id] = record
        return record

    async def get(self, thread_id: str) -> ThreadRecord | None:
        return self.threads.get(thread_id)

    async def append_turn(self, turn: TurnRecord) -> None:
        self.turns[turn.thread_id].append(turn)
        current = self.threads[turn.thread_id]
        self.threads[turn.thread_id] = ThreadRecord(
            thread_id=current.thread_id,
            client_id=current.client_id,
            channel=current.channel,
            created_at=current.created_at,
            frozen=current.frozen,
            turn_count=current.turn_count + 1,
        )

    async def list_turns(
        self, *, thread_id: str, cursor: str | None, limit: int
    ) -> tuple[list[TurnRecord], str | None]:
        turns = sorted(self.turns.get(thread_id, []), key=lambda t: (t.created_at, t.turn_id))
        if cursor:
            after_ts, after_id = _decode_cursor(cursor)
            turns = [t for t in turns if (t.created_at, t.turn_id) > (after_ts, after_id)]
        page = turns[:limit]
        next_cursor = (
            _encode_cursor(page[-1].created_at, page[-1].turn_id) if len(turns) > limit else None
        )
        return page, next_cursor

    async def set_frozen(self, thread_id: str, *, frozen: bool) -> None:
        current = self.threads[thread_id]
        self.threads[thread_id] = ThreadRecord(
            thread_id=current.thread_id,
            client_id=current.client_id,
            channel=current.channel,
            created_at=current.created_at,
            frozen=frozen,
            turn_count=current.turn_count,
        )

    async def list_for_client(self, client_id: str) -> list[ThreadRecord]:
        return [t for t in self.threads.values() if t.client_id == client_id]

    async def health(self) -> bool:
        return True


class MemoryConsentRepository:
    def __init__(self) -> None:
        self.records: list[ConsentRecord] = []

    async def list_for_client(self, client_id: str) -> list[ConsentRecord]:
        return [c for c in self.records if c.client_id == client_id]

    async def record(self, consent: ConsentRecord) -> None:
        self.records.append(consent)

    async def revoke(self, *, client_id: str, type: ConsentType, at: datetime) -> bool:
        revoked = False
        for i, c in enumerate(self.records):
            if c.client_id == client_id and c.type is type and c.granted and c.revoked_at is None:
                self.records[i] = c.model_copy(update={"revoked_at": at})
                revoked = True
        return revoked

    async def has_active(self, *, client_id: str, type: ConsentType, version: str | None) -> bool:
        return any(
            c.client_id == client_id
            and c.type is type
            and c.granted
            and c.revoked_at is None
            and (version is None or c.version == version)
            for c in self.records
        )


class MemoryDeviceRepository:
    def __init__(self) -> None:
        self.bindings: dict[tuple[str, str], DeviceBinding] = {}

    async def get(self, *, client_id: str, jkt: str) -> DeviceBinding | None:
        return self.bindings.get((client_id, jkt))

    async def register(self, binding: DeviceBinding) -> None:
        self.bindings[(binding.client_id, binding.jkt)] = binding


class MemoryFormSpecRepository:
    def __init__(self) -> None:
        self.specs: dict[str, tuple[FormSpec, str]] = {}
        self.submissions: list[dict[str, Any]] = []

    async def store(self, spec: FormSpec, *, status: str) -> None:
        self.specs[spec.form_id] = (spec, status)

    async def get(self, form_id: str) -> tuple[FormSpec, str] | None:
        return self.specs.get(form_id)

    async def mark(self, form_id: str, *, status: str) -> None:
        spec, _ = self.specs[form_id]
        self.specs[form_id] = (spec, status)

    async def record_submission(self, **kwargs: Any) -> None:
        self.submissions.append({**kwargs, "submitted_at": datetime.now(UTC)})


class MemoryIdempotencyRepository:
    def __init__(self) -> None:
        self.entries: dict[str, tuple[str, dict[str, Any], float]] = {}

    async def get(self, key: str) -> tuple[str, dict[str, Any]] | None:
        item = self.entries.get(key)
        if item is None:
            return None
        request_hash, response, expires = item
        if expires < time.monotonic():
            del self.entries[key]
            return None
        return request_hash, response

    async def put(
        self, key: str, *, request_hash: str, response: dict[str, Any], ttl_s: int
    ) -> None:
        self.entries[key] = (request_hash, response, time.monotonic() + ttl_s)


class MemoryChallengeRepository:
    def __init__(self) -> None:
        self.challenges: dict[str, dict[str, Any]] = {}

    async def store(
        self,
        *,
        challenge_id: str,
        client_id: str,
        form_id: str,
        amount_hash: str,
        nonce: str,
        expires_at: datetime,
    ) -> None:
        self.challenges[challenge_id] = {
            "challenge_id": challenge_id,
            "client_id": client_id,
            "form_id": form_id,
            "amount_hash": amount_hash,
            "nonce": nonce,
            "expires_at": expires_at.isoformat(),
            "used_at": None,
        }

    async def consume(self, *, challenge_id: str, client_id: str) -> dict[str, Any] | None:
        row = self.challenges.get(challenge_id)
        if row is None or row["client_id"] != client_id or row["used_at"] is not None:
            return None
        row["used_at"] = datetime.now(UTC).isoformat()
        return dict(row)


class MemoryAvatarSessionRepository:
    def __init__(self) -> None:
        self.sessions: dict[str, AvatarSessionRecord] = {}

    async def create(self, record: AvatarSessionRecord) -> None:
        self.sessions[record.avatar_session_id] = record

    async def finish(
        self,
        avatar_session_id: str,
        *,
        ended_at: datetime,
        duration_s: float,
        speaking_s: float,
        end_reason: str,
    ) -> None:
        current = self.sessions[avatar_session_id]
        self.sessions[avatar_session_id] = AvatarSessionRecord(
            avatar_session_id=current.avatar_session_id,
            client_id=current.client_id,
            thread_id=current.thread_id,
            vendor_session_id=current.vendor_session_id,
            started_at=current.started_at,
            ended_at=ended_at,
            duration_s=duration_s,
            speaking_s=speaking_s,
            end_reason=end_reason,
        )

    async def minutes_used_today(self, client_id: str) -> float:
        today = datetime.now(UTC).date()
        seconds = 0.0
        for s in self.sessions.values():
            if s.client_id == client_id and s.started_at.date() == today:
                seconds += (
                    s.duration_s
                    if s.ended_at
                    else (datetime.now(UTC) - s.started_at).total_seconds()
                )
        return seconds / 60

    async def get(self, avatar_session_id: str) -> AvatarSessionRecord | None:
        return self.sessions.get(avatar_session_id)


class MemoryEvidenceIndexRepository:
    def __init__(self) -> None:
        self.rows: dict[str, EvidenceIndexRow] = {}

    async def index(self, row: EvidenceIndexRow) -> None:
        self.rows[row.evidence_id] = row

    async def query(
        self,
        *,
        client_id: str | None,
        thread_id: str | None,
        since: datetime | None,
        until: datetime | None,
        service_type: str | None,
        product_id: str | None,
        refused: bool | None,
        limit: int,
        cursor: str | None,
    ) -> tuple[list[EvidenceIndexRow], str | None]:
        rows = sorted(self.rows.values(), key=lambda r: (r.created_at, r.evidence_id))
        rows = [
            r
            for r in rows
            if (client_id is None or r.client_id == client_id)
            and (thread_id is None or r.thread_id == thread_id)
            and (since is None or r.created_at >= since)
            and (until is None or r.created_at <= until)
            and (service_type is None or r.service_type == service_type)
            and (product_id is None or product_id in r.product_ids)
            and (refused is None or r.refused == refused)
        ]
        if cursor:
            after_ts, after_id = _decode_cursor(cursor)
            rows = [r for r in rows if (r.created_at, r.evidence_id) > (after_ts, after_id)]
        page = rows[:limit]
        next_cursor = (
            _encode_cursor(page[-1].created_at, page[-1].evidence_id) if len(rows) > limit else None
        )
        return page, next_cursor

    async def get(self, evidence_id: str) -> EvidenceIndexRow | None:
        return self.rows.get(evidence_id)

    async def set_legal_hold(self, *, thread_id: str, on: bool) -> int:
        count = 0
        for evidence_id, row in list(self.rows.items()):
            if row.thread_id == thread_id:
                self.rows[evidence_id] = dataclasses.replace(row, legal_hold=on)
                count += 1
        return count

    async def counts(self, *, since: datetime, until: datetime) -> dict[str, Any]:
        rows = [r for r in self.rows.values() if since <= r.created_at <= until]
        by_service: dict[str, int] = defaultdict(int)
        by_intent: dict[str, int] = defaultdict(int)
        for r in rows:
            by_service[r.service_type] += 1
            by_intent[r.intent] += 1
        return {
            "evidence_records": len(rows),
            "turns_by_service_type": dict(by_service),
            "turns_by_intent": dict(by_intent),
            "refusals": sum(1 for r in rows if r.refused),
        }


class MemoryAccessLogRepository:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    async def log(self, *, actor: str, action: str, scope: dict[str, Any], reason: str) -> None:
        self.entries.append(
            {
                "at": datetime.now(UTC),
                "actor": actor,
                "action": action,
                "scope": scope,
                "reason": reason,
            }
        )


class MemoryArcoRepository:
    def __init__(self) -> None:
        self.requests: dict[str, dict[str, Any]] = {}

    async def open_request(
        self, *, request_id: str, client_id: str, kind: str, opened_at: datetime
    ) -> None:
        self.requests[request_id] = {
            "request_id": request_id,
            "client_id": client_id,
            "kind": kind,
            "opened_at": opened_at,
            "closed_at": None,
            "export_key": None,
        }

    async def close_request(
        self, *, request_id: str, closed_at: datetime, export_key: str | None
    ) -> None:
        self.requests[request_id].update({"closed_at": closed_at, "export_key": export_key})

    async def list_requests(self, *, client_id: str | None) -> list[dict[str, Any]]:
        return [
            r for r in self.requests.values() if client_id is None or r["client_id"] == client_id
        ]


class MemoryRulesetRepository:
    def __init__(self) -> None:
        self.versions: dict[int, dict[str, Any]] = {}

    async def record_version(
        self, *, version: int, rules: list[dict[str, Any]], published_at: datetime
    ) -> None:
        self.versions.setdefault(version, {"rules": rules, "published_at": published_at})

    async def list_versions(self) -> list[int]:
        return sorted(self.versions)


class MemoryAudioSegmentRepository:
    def __init__(self) -> None:
        self.segments: list[dict[str, Any]] = []

    async def record(
        self,
        *,
        thread_id: str,
        turn_id: str,
        segment_id: str,
        object_key: str,
        speaker: str,
        consent_version: str,
        created_at: datetime,
    ) -> None:
        self.segments.append(
            {
                "thread_id": thread_id,
                "turn_id": turn_id,
                "segment_id": segment_id,
                "object_key": object_key,
                "speaker": speaker,
                "consent_version": consent_version,
                "created_at": created_at,
            }
        )

    async def count_without_consent(self) -> int:
        return sum(1 for s in self.segments if not s["consent_version"])


@dataclass
class MemoryRepositories:
    """Convenience bundle mirroring ``deps.Repositories``."""

    threads: MemoryThreadRepository = field(default_factory=MemoryThreadRepository)
    consents: MemoryConsentRepository = field(default_factory=MemoryConsentRepository)
    devices: MemoryDeviceRepository = field(default_factory=MemoryDeviceRepository)
    form_specs: MemoryFormSpecRepository = field(default_factory=MemoryFormSpecRepository)
    idempotency: MemoryIdempotencyRepository = field(default_factory=MemoryIdempotencyRepository)
    challenges: MemoryChallengeRepository = field(default_factory=MemoryChallengeRepository)
    avatar_sessions: MemoryAvatarSessionRepository = field(
        default_factory=MemoryAvatarSessionRepository
    )
    evidence_index: MemoryEvidenceIndexRepository = field(
        default_factory=MemoryEvidenceIndexRepository
    )
    access_log: MemoryAccessLogRepository = field(default_factory=MemoryAccessLogRepository)
    arco: MemoryArcoRepository = field(default_factory=MemoryArcoRepository)
    rulesets: MemoryRulesetRepository = field(default_factory=MemoryRulesetRepository)
    audio_segments: MemoryAudioSegmentRepository = field(
        default_factory=MemoryAudioSegmentRepository
    )
