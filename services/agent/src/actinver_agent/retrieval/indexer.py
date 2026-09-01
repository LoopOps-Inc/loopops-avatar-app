"""Embedding pipeline with the client-data classifier (ADR-0014 enforcement).

Every chunk is classified before indexing; anything matching a client
identifier pattern or a client-specific marker is rejected and alerted. A CI
test indexes a synthetic identifier and asserts rejection (control AI-08).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

import structlog

from actinver_agent.guardrails import patterns as pat
from actinver_agent.observability.setup import get_metrics
from actinver_agent.ports import Embedder
from actinver_agent.retrieval.ports import COLLECTIONS, Chunk, VectorStorePort

log = structlog.get_logger(__name__)

_CLIENT_MARKERS = re.compile(
    r"\b(cliente\s+n[uú]mero|client_id|cl_[a-z0-9]{4,}|saldo\s+de\s+[A-ZÁÉÍÓÚ][a-záéíóú]+\s+[A-Z]|"
    r"posici[oó]n\s+de\s+[A-ZÁÉÍÓÚ][a-záéíóú]+\s+[A-ZÁÉÍÓÚ])",
    re.IGNORECASE,
)

_CHUNK_WORDS = 800
_OVERLAP_WORDS = 100


class ClientDataRejected(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Classification:
    accepted: bool
    reasons: tuple[str, ...]


def classify_chunk(text: str) -> Classification:
    reasons: list[str] = [f"IDENTIFIER_{k}" for k in pat.scan_identifiers(text)]
    if _CLIENT_MARKERS.search(text):
        reasons.append("CLIENT_MARKER")
    return Classification(accepted=not reasons, reasons=tuple(reasons))


def chunk_text(text: str, *, words: int = _CHUNK_WORDS, overlap: int = _OVERLAP_WORDS) -> list[str]:
    tokens = text.split()
    if len(tokens) <= words:
        return [" ".join(tokens)] if tokens else []
    out: list[str] = []
    start = 0
    while start < len(tokens):
        out.append(" ".join(tokens[start : start + words]))
        if start + words >= len(tokens):
            break
        start += words - overlap
    return out


class Indexer:
    def __init__(self, embedder: Embedder, store: VectorStorePort) -> None:
        self._embedder = embedder
        self._store = store

    async def index_document(
        self,
        *,
        collection: str,
        doc_id: str,
        title: str,
        source: str,
        published_at: datetime | None,
        text: str,
    ) -> int:
        if collection not in COLLECTIONS:
            raise ValueError(f"unknown collection {collection!r}")
        pieces = chunk_text(text)
        accepted: list[str] = []
        for piece in pieces:
            verdict = classify_chunk(f"{title}\n{piece}")
            if not verdict.accepted:
                # Rejections alert: client data must never reach the corpus.
                log.error(
                    "retrieval.client_data_rejected",
                    collection=collection,
                    doc_id=doc_id,
                    reasons=list(verdict.reasons),
                    security_event=True,
                )
                get_metrics().dlp_hits.add(1, {"stage": "embedding", "collection": collection})
                raise ClientDataRejected(", ".join(verdict.reasons))
            accepted.append(piece)
        if not accepted:
            return 0
        embeddings = await self._embedder.embed(accepted)
        chunks = [
            Chunk(
                collection=collection,
                doc_id=doc_id,
                title=title,
                source=source,
                published_at=published_at,
                content=piece,
                embedding=embedding,
            )
            for piece, embedding in zip(accepted, embeddings, strict=True)
        ]
        return await self._store.upsert(chunks)
