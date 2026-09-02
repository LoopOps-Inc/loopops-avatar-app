"""Thread identity, shared by every repository implementation.

The reference architecture derived the id from
``sha256(client_id || channel || salt)`` (docs/01-architecture/04 §3.1), which
gave one person a separate conversation per channel: what they said out loud
was invisible when they typed. The channel is deliberately no longer part of
the identity, so chat and voice continue the same thread.

Nothing auditable depends on the split: every turn stores its own channel
(``TurnRecord.channel``, returned per turn by ``GET /v1/threads/{id}``) and
consents are keyed by client. ``threads.channel`` now records the channel the
conversation started in.
"""

from __future__ import annotations

import hashlib


def derive_thread_id(client_id: str, *, salt: str) -> str:
    """Deterministic, salted, one per client."""
    return "th_" + hashlib.sha256(f"{client_id}|{salt}".encode()).hexdigest()[:24]
