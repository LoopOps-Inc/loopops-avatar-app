"""Turn events: the single stream shape consumed by the SSE route (chat) and the
audio WebSocket handler (voice). Mirrors docs/04-backend/04 §2.

``done`` always fires, including after ``error``, so every client state machine
has exactly one terminal event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

TurnEventKind = Literal[
    "thinking",  # voice only: emitted immediately when the run starts
    "filler",  # voice only: a pre-synthesised acknowledgement was played
    "token",  # approved narrative text, sentence-chunked
    "ui",  # one UIComponent (dict) - exact figures, cards, forms
    "form_spec",  # the signed FormSpec (dict)
    "citations",  # {"items": [...]}
    "error",  # {"code", "message", "escalate"} - in-stream 200, not HTTP
    "done",  # {"turn_id", "evidence_id", "service_type", ...}
]


@dataclass(frozen=True, slots=True)
class TurnEvent:
    kind: TurnEventKind
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TurnOutcome:
    """What a completed turn produced, for persistence and voice synthesis."""

    turn_id: str
    thread_id: str
    speech: str | None
    ui_payload: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    form_spec: dict[str, Any] | None
    error: dict[str, Any] | None
    evidence_id: str | None
    service_type: str
    service_subtype: str
    intent: str | None
    degraded_from: str | None
    disclosures_shown: dict[str, str]
    interrupted: bool = False
    elapsed_ms: int = 0
