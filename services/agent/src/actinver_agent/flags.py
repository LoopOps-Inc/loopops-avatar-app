"""Feature flags and the kill switch (ADR-0015).

Every capability is independently flagged. Defaults live here; runtime
overrides come from the flag store (Redis key ``flags:{name}``) so a flip
propagates in seconds from a path independent of the deployment pipeline.
Every flag carries an ``expires_at``; an expired flag fails the build
(``tests/assertions/test_flags_unexpired.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FlagSpec:
    name: str
    default: str
    owner: str
    expires_at: date
    description: str


#: The flag inventory from ADR-0015. Regulated flags are owned by Compliance.
FLAGS: tuple[FlagSpec, ...] = (
    FlagSpec(
        "advisor.enabled",
        "on",
        "Product",
        date(2027, 9, 1),
        "Master switch for the assistant entry points",
    ),
    FlagSpec(
        "advisor.voice_mode", "on", "Product", date(2027, 9, 1), "Offer voice mode to clients"
    ),
    FlagSpec(
        "advisor.avatar", "on", "Product", date(2027, 9, 1), "Start LiveAvatar sessions (LITE mode)"
    ),
    FlagSpec(
        "advisor.intent.advisory_recommend",
        "on",
        "Compliance",
        date(2027, 9, 1),
        "Allow the regulated advisory path (asesoría de inversiones)",
    ),
    FlagSpec(
        "advisor.intent.transactional",
        "on",
        "Compliance",
        date(2027, 9, 1),
        "Allow transactional planning (Form Specs)",
    ),
    FlagSpec(
        "advisor.model.primary",
        "gemini-2.5-flash",
        "Engineering",
        date(2027, 9, 1),
        "Primary model for informational intents",
    ),
    FlagSpec(
        "advisor.suitability.ruleset_version",
        "14",
        "Compliance",
        date(2027, 9, 1),
        "Pinned suitability ruleset version",
    ),
    FlagSpec(
        "advisor.prompt.version",
        "advisor-es-MX@2026-08-20",
        "Compliance",
        date(2027, 9, 1),
        "Pinned system prompt version",
    ),
    FlagSpec(
        "advisor.kill_switch",
        "off",
        "Risk",
        date(2027, 9, 1),
        "Disables generation without a deploy. Risk has unilateral authority.",
    ),
)

FLAG_INDEX: dict[str, FlagSpec] = {f.name: f for f in FLAGS}

#: Legal-approved static text returned while the kill switch is on. Do not
#: improvise wording under incident pressure (RB-07).
KILL_SWITCH_MESSAGE_ES = (
    "El asistente digital no está disponible por el momento. "
    "Tu asesor puede atenderte; ¿te comunicamos con él?"
)


class FlagStore(Protocol):
    async def get_flag(self, name: str) -> str | None: ...
    async def set_flag(self, name: str, value: str) -> None: ...


class FeatureFlags:
    def __init__(self, store: FlagStore | None) -> None:
        self._store = store

    async def get(self, name: str) -> str:
        spec = FLAG_INDEX[name]
        if self._store is None:
            return spec.default
        try:
            value = await self._store.get_flag(name)
        except Exception:
            log.warning("flags.store_unavailable", flag=name)
            return spec.default if name != "advisor.kill_switch" else "off"
        return value if value is not None else spec.default

    async def is_on(self, name: str) -> bool:
        return (await self.get(name)).lower() in {"on", "true", "1", "yes"}

    async def kill_switch_active(self) -> bool:
        return await self.is_on("advisor.kill_switch")

    async def set(self, name: str, value: str, *, actor: str) -> None:
        spec = FLAG_INDEX[name]
        if self._store is None:
            raise RuntimeError("no flag store configured")
        await self._store.set_flag(name, value)
        log.warning("flags.changed", flag=name, value=value, owner=spec.owner, actor=actor)


def unexpired(today: date | None = None) -> list[FlagSpec]:
    today = today or datetime.now(UTC).date()
    return [f for f in FLAGS if f.expires_at <= today]
