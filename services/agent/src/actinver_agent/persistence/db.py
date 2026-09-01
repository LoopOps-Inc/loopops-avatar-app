"""Async database engine and RLS identity scoping.

Row-level security policies (migration 0001) read ``app.client_id`` and
``app.service_identity``; ``identity_scope`` sets them ``LOCAL`` to the
transaction so a repository can only see the rows its caller may see. Network
position is never authorisation (docs/04-backend/02 §4).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_IDENTITY_RE = r"^[A-Za-z0-9_\-:.]{1,120}$"


def create_engine(
    database_url: SecretStr, *, pool_size: int = 10, max_overflow: int = 5
) -> AsyncEngine:
    """Pool size derived from measured concurrency, not copied from a tutorial;
    exhaustion produces a fast explicit error (``pool_timeout``) rather than a
    queue that blows the latency budget."""
    return create_async_engine(
        database_url.get_secret_value(),
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=2.0,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _quote_identity(value: str) -> str:
    import re

    if re.match(_IDENTITY_RE, value) is None:
        raise ValueError("invalid identity value")
    return value.replace("'", "''")


@asynccontextmanager
async def identity_scope(
    session: AsyncSession, *, client_id: str | None, service_identity: str
) -> AsyncIterator[AsyncSession]:
    """Open a transaction with the RLS identity bound."""
    async with session.begin():
        await session.execute(
            text(f"SET LOCAL app.service_identity = '{_quote_identity(service_identity)}'")
        )
        if client_id is not None:
            await session.execute(text(f"SET LOCAL app.client_id = '{_quote_identity(client_id)}'"))
        yield session


async def health(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
