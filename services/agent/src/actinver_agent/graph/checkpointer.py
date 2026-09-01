"""LangGraph checkpointer factory.

Postgres (``AsyncPostgresSaver``) gives durable checkpoints so a transaction
interrupt survives a pod restart and resumes on another replica (ADR-0004).
``InMemorySaver`` is for unit tests and single-process demos only.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any

import structlog

from actinver_agent.config import Settings

log = structlog.get_logger(__name__)

Closer = Callable[[], Awaitable[None]]


def make_serializer() -> Any:
    """Checkpoints carry our typed state; allow exactly those classes and nothing else."""
    import inspect

    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    from actinver_agent.graph import state as state_module

    allowed = [
        (state_module.__name__, name)
        for name, obj in vars(state_module).items()
        if inspect.isclass(obj) and obj.__module__ == state_module.__name__
    ]
    return JsonPlusSerializer(allowed_msgpack_modules=allowed)


def _psycopg_url(url: str) -> str:
    """The checkpointer uses psycopg; the ORM uses asyncpg. Same database."""
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )


async def make_checkpointer(settings: Settings) -> tuple[Any, Closer | None]:
    if settings.checkpointer_provider == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver(serde=make_serializer()), None

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    stack = AsyncExitStack()
    saver = await stack.enter_async_context(
        AsyncPostgresSaver.from_conn_string(_psycopg_url(settings.database_url.get_secret_value()))
    )
    await saver.setup()
    log.info("checkpointer.ready", provider="postgres")

    async def close() -> None:
        await stack.aclose()

    return saver, close
