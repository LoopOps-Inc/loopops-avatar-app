"""Backend wiring shared by the control services (audit, transaction) and
reusable by the agent process: object store, secrets, repositories.

Provider SDKs are only touched through ``adapters/``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from actinver_agent.config import Settings
from actinver_agent.deps import Repositories
from actinver_agent.persistence import memory
from actinver_agent.persistence.bootstrap import create_memory_repositories, create_repositories
from actinver_agent.persistence.db import create_engine, create_session_factory
from actinver_agent.persistence.repositories import SqlChainStore, SqlSpool
from actinver_agent.ports import (
    AuditPort,
    CachePort,
    ChainStorePort,
    CoreBankingPort,
    ObjectStorePort,
    OmsPort,
    SecretsBackendPort,
    SpoolPort,
)
from actinver_agent.secrets import SecretResolver

Closer = Callable[[], Awaitable[None]]


def build_secrets_backend(settings: Settings) -> SecretsBackendPort | None:
    """AWS Secrets Manager (floci locally). ``None`` when only env/file refs are used."""
    if not settings.secrets.manager_endpoint:
        return None
    import os

    from actinver_agent.adapters.aws_secrets import AwsSecretsManager

    return AwsSecretsManager(
        endpoint=settings.secrets.manager_endpoint,
        region=settings.secrets.manager_region,
        access_key=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )


def build_resolver(settings: Settings) -> SecretResolver:
    return SecretResolver(settings=settings, manager=build_secrets_backend(settings))


async def build_object_store(
    settings: Settings, resolver: SecretResolver, *, bucket: str | None = None
) -> ObjectStorePort:
    if settings.object_store.provider == "memory":
        return memory.MemoryObjectStore()
    from actinver_agent.adapters.s3_store import S3ObjectStore

    access_key = await resolver.try_resolve(settings.object_store.access_key_ref) or "test"
    secret_key = await resolver.try_resolve(settings.object_store.secret_key_ref) or "test"
    return S3ObjectStore(
        endpoint=settings.object_store.endpoint,
        region=settings.object_store.region,
        bucket=bucket or settings.object_store.bucket,
        access_key=access_key,
        secret_key=secret_key,
        lock_mode=settings.object_store.lock_mode,
    )


async def build_cache(settings: Settings) -> tuple[CachePort, Closer | None]:
    if settings.cache_provider == "memory":
        return memory.MemoryCache(), None
    from actinver_agent.adapters.redis_cache import RedisCache

    cache = RedisCache(settings.redis_url.get_secret_value())
    return cache, cache.aclose


@dataclass
class SqlBackends:
    repos: Repositories
    chain: ChainStorePort
    spool: SpoolPort
    closers: list[Closer] = field(default_factory=list)
    sessions: Any = None


def build_sql_backends(settings: Settings, *, service_identity: str) -> SqlBackends:
    if settings.checkpointer_provider == "memory" and settings.cache_provider == "memory":
        # Fully in-memory posture (unit tests, single-process demos).
        return SqlBackends(
            repos=create_memory_repositories(),
            chain=memory.MemoryChainStore(),
            spool=memory.MemorySpool(),
        )
    engine = create_engine(settings.database_url)
    sessions = create_session_factory(engine)
    return SqlBackends(
        repos=create_repositories(sessions, engine=engine, service_identity=service_identity),
        chain=SqlChainStore(sessions, service_identity=service_identity),
        spool=SqlSpool(sessions, service_identity=service_identity),
        closers=[engine.dispose],
        sessions=sessions,
    )


@dataclass
class AuditBackends:
    store: ObjectStorePort
    anchor_store: ObjectStorePort | None
    chain: ChainStorePort
    spool: SpoolPort
    index: Any
    access_log: Any
    closers: list[Closer] = field(default_factory=list)

    async def aclose(self) -> None:
        for closer in self.closers:
            await closer()


async def build_audit_backends(settings: Settings, resolver: SecretResolver) -> AuditBackends:
    sql = build_sql_backends(settings, service_identity="audit_svc")
    store = await build_object_store(settings, resolver)
    anchor_store = await build_object_store(
        settings, resolver, bucket=f"{settings.object_store.bucket}-anchor"
    )
    return AuditBackends(
        store=store,
        anchor_store=anchor_store,
        chain=sql.chain,
        spool=sql.spool,
        index=sql.repos.evidence_index,
        access_log=sql.repos.access_log,
        closers=sql.closers,
    )


@dataclass
class TransactionBackends:
    core: CoreBankingPort
    oms: OmsPort
    repos: Repositories
    audit: AuditPort
    form_key: bytes
    closers: list[Closer] = field(default_factory=list)

    async def aclose(self) -> None:
        for closer in self.closers:
            await closer()


async def build_transaction_backends(
    settings: Settings, resolver: SecretResolver
) -> TransactionBackends:
    import httpx

    sql = build_sql_backends(settings, service_identity="txn_svc")
    if settings.core_provider == "synthetic":
        from actinver_agent.clients.synthetic import SyntheticCoreBanking, SyntheticOms

        core: CoreBankingPort = SyntheticCoreBanking()
        oms: OmsPort = SyntheticOms()
    else:  # pragma: no cover - needs the core inventory
        from actinver_agent.clients.core_http import CoreBankingHttp
        from actinver_agent.clients.oms_http import OmsHttp

        core = CoreBankingHttp(settings)
        oms = OmsHttp(settings, base_url=settings.oms_base_url)

    closers = list(sql.closers)
    audit: AuditPort
    if settings.services.audit_url == "inprocess":
        from actinver_agent.audit.inprocess import InProcessAudit
        from actinver_agent.audit.sink import EvidenceWriter

        store = await build_object_store(settings, resolver)
        audit = InProcessAudit(
            EvidenceWriter(
                store=store,
                chain=sql.chain,
                index=sql.repos.evidence_index,
                spool=sql.spool,
                lock_mode=settings.object_store.lock_mode,
                retention_years=settings.object_store.retention_years,
            )
        )
    else:
        from actinver_agent.audit.client import HttpAudit

        http = httpx.AsyncClient()
        closers.append(http.aclose)
        audit = HttpAudit(
            settings.services.audit_url, http, timeout_s=settings.services.request_timeout_s
        )

    form_key = await resolver.resolve_bytes(settings.form_spec_signing_key_ref)
    return TransactionBackends(
        core=core, oms=oms, repos=sql.repos, audit=audit, form_key=form_key, closers=closers
    )
