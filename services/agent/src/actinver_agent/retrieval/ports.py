"""Vector store port for the retrieval corpus (research notes, product docs,
policy FAQ, regulatory disclosures). No client-specific data is ever indexed."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

COLLECTIONS: tuple[str, ...] = (
    "research_notes",
    "product_docs",
    "policy_faq",
    "regulatory_disclosures",
)


@dataclass(frozen=True, slots=True)
class Chunk:
    collection: str
    doc_id: str
    title: str
    source: str
    published_at: datetime | None
    content: str
    embedding: list[float] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Hit:
    chunk: Chunk
    score: float


class VectorStorePort(Protocol):
    async def upsert(self, chunks: list[Chunk]) -> int: ...
    async def search(self, collection: str, embedding: list[float], k: int) -> list[Hit]: ...
    async def count(self, collection: str) -> int: ...
