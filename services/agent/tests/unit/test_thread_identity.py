"""One thread per client, so chat and voice share a memory.

The reference architecture derived the id from
``sha256(client_id || channel || salt)``, which gave the same person a separate
conversation per channel: what they said out loud was invisible when they typed.
Auditing does not depend on the split - every turn records its own channel
(``TurnRecord.channel``, surfaced per turn by GET /v1/threads/{id}) and consents
are keyed by client, not by channel.
"""

from __future__ import annotations

from actinver_agent.persistence.thread_id import derive_thread_id


def test_chat_and_voice_resolve_to_the_same_thread() -> None:
    assert derive_thread_id("200008", salt="s") == derive_thread_id("200008", salt="s")


def test_different_clients_never_share_a_thread() -> None:
    assert derive_thread_id("200001", salt="s") != derive_thread_id("200008", salt="s")


def test_the_salt_separates_deployments() -> None:
    assert derive_thread_id("200008", salt="a") != derive_thread_id("200008", salt="b")


def test_the_id_is_prefixed_and_bounded() -> None:
    thread_id = derive_thread_id("200008", salt="s")

    assert thread_id.startswith("th_")
    assert len(thread_id) == 27
