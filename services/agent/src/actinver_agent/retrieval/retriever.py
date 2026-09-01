"""Retriever and the two vector-store implementations.

``Retriever`` has no access to ``client_id`` by construction: it cannot build a
client-filtered query even by mistake (ADR-0014 enforcement).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

import structlog

from actinver_agent.ports import Embedder
from actinver_agent.retrieval.ports import Chunk, Hit, VectorStorePort

log = structlog.get_logger(__name__)


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class MemoryVectorStore:
    def __init__(self) -> None:
        self._chunks: dict[tuple[str, str, int], Chunk] = {}

    async def upsert(self, chunks: list[Chunk]) -> int:
        for index, chunk in enumerate(chunks):
            key = (chunk.collection, chunk.doc_id, hash(chunk.content) ^ index)
            self._chunks[key] = chunk
        return len(chunks)

    async def search(self, collection: str, embedding: list[float], k: int) -> list[Hit]:
        scored = [
            Hit(chunk=c, score=cosine(embedding, c.embedding))
            for c in self._chunks.values()
            if c.collection == collection
        ]
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]

    async def count(self, collection: str) -> int:
        return sum(1 for c in self._chunks.values() if c.collection == collection)


class PgVectorStore:
    """pgvector over ``retrieval.chunks`` (``embedding vector(768)``)."""

    def __init__(self, session_factory: Any) -> None:
        self._sessions = session_factory

    async def upsert(self, chunks: list[Chunk]) -> int:
        from sqlalchemy import text

        async with self._sessions() as session:
            for chunk in chunks:
                await session.execute(
                    text(
                        "INSERT INTO retrieval.chunks (collection, doc_id, title, source, "
                        "published_at, content, embedding_json, embedding) VALUES "
                        "(:collection, :doc_id, :title, :source, :published_at, :content, "
                        "CAST(:embedding_json AS jsonb), CAST(:embedding AS vector))"
                    ),
                    {
                        "collection": chunk.collection,
                        "doc_id": chunk.doc_id,
                        "title": chunk.title,
                        "source": chunk.source,
                        "published_at": chunk.published_at,
                        "content": chunk.content,
                        "embedding_json": _json_list(chunk.embedding),
                        "embedding": _pg_vector(chunk.embedding),
                    },
                )
            await session.commit()
        return len(chunks)

    async def search(self, collection: str, embedding: list[float], k: int) -> list[Hit]:
        from sqlalchemy import text

        async with self._sessions() as session:
            rows = await session.execute(
                text(
                    "SELECT doc_id, title, source, published_at, content, "
                    "1 - (embedding <=> CAST(:embedding AS vector)) AS score "
                    "FROM retrieval.chunks WHERE collection = :collection "
                    "ORDER BY embedding <=> CAST(:embedding AS vector) LIMIT :k"
                ),
                {"embedding": _pg_vector(embedding), "collection": collection, "k": k},
            )
            return [
                Hit(
                    chunk=Chunk(
                        collection=collection,
                        doc_id=r.doc_id,
                        title=r.title,
                        source=r.source,
                        published_at=r.published_at,
                        content=r.content,
                    ),
                    score=float(r.score),
                )
                for r in rows
            ]

    async def count(self, collection: str) -> int:
        from sqlalchemy import text

        async with self._sessions() as session:
            result = await session.execute(
                text("SELECT count(*) FROM retrieval.chunks WHERE collection = :c"),
                {"c": collection},
            )
            return int(result.scalar_one())


def _pg_vector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


def _json_list(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in values) + "]"


class Retriever:
    def __init__(self, embedder: Embedder, store: VectorStorePort) -> None:
        self._embedder = embedder
        self._store = store

    @property
    def store(self) -> VectorStorePort:
        return self._store

    async def search(self, collection: str, query: str, k: int = 4) -> list[Hit]:
        [embedding] = await self._embedder.embed([query])
        return await self._store.search(collection, embedding, k)

    async def search_as_tool(self, collection: str, *, query: str, k: int = 4) -> dict[str, Any]:
        """Tool-shaped result: items with title/source/date/summary so the
        composer renders citations and the guardrail scans the text."""
        hits = await self.search(collection, query, k)
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "items": [
                {
                    "title": h.chunk.title,
                    "source": h.chunk.source,
                    "published_at": h.chunk.published_at.isoformat()
                    if h.chunk.published_at
                    else None,
                    "summary": h.chunk.content[:600],
                    "url": None,
                    "ref": f"{h.chunk.collection}:{h.chunk.doc_id}",
                    "score": round(h.score, 4),
                }
                for h in hits
            ],
        }
