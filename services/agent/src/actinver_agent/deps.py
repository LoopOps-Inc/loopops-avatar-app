"""Dependency wiring.

One ``Dependencies`` object per process, built at startup by ``build_dependencies``
and torn down at shutdown. Everything the graph, the API routes, the broker and
the voice pipeline need hangs off it, typed by the ports in ``ports.py``.

The concrete adapters chosen depend on ``Settings``:

* ``*_url == "inprocess"``  → the control runs as a library in this process
  (tests, single-binary dev). Otherwise an HTTP client to the separately
  deployed service is used (docker compose / Kubernetes).
* ``core_provider``         → ``synthetic`` (deterministic demo core) or ``http``.
* ``llm.provider``          → ``stub`` / ``vertex`` / ``gemini_api``.
* ``voice.provider``, ``avatar.provider``, ``cache_provider``,
  ``checkpointer_provider``, ``object_store.provider`` likewise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from actinver_agent.config import Settings
from actinver_agent.flags import FeatureFlags
from actinver_agent.observability.setup import Metrics
from actinver_agent.ports import (
    AccessLogRepository,
    ArcoRepository,
    AudioSegmentRepository,
    AuditPort,
    AvatarSessionRepository,
    AvatarVendorPort,
    CachePort,
    ChainStorePort,
    ChallengeRepository,
    ConsentRepository,
    CoreBankingPort,
    CrmPort,
    DeviceRepository,
    Embedder,
    EvidenceIndexRepository,
    FormSpecRepository,
    Generator,
    GuardrailPort,
    IdempotencyRepository,
    IntentClassifier,
    MarketDataPort,
    NewsPort,
    ObjectStorePort,
    OmsPort,
    Planner,
    RulesetRepository,
    SpeechToTextPort,
    SpoolPort,
    SuitabilityPort,
    TextToSpeechPort,
    ThreadRepository,
    TransactionPort,
)
from actinver_agent.secrets import SecretResolver

if TYPE_CHECKING:
    from actinver_agent.avatar.broker import AvatarBroker
    from actinver_agent.graph.runtime import TurnRunner
    from actinver_agent.llm.prompts import PromptLibrary
    from actinver_agent.tools.gateway import ToolGateway
    from actinver_agent.tools.registry import ToolRegistry


@dataclass
class Repositories:
    threads: ThreadRepository
    consents: ConsentRepository
    devices: DeviceRepository
    form_specs: FormSpecRepository
    idempotency: IdempotencyRepository
    challenges: ChallengeRepository
    avatar_sessions: AvatarSessionRepository
    evidence_index: EvidenceIndexRepository
    access_log: AccessLogRepository
    arco: ArcoRepository
    rulesets: RulesetRepository
    audio_segments: AudioSegmentRepository


@dataclass
class Dependencies:
    settings: Settings
    secrets: SecretResolver
    flags: FeatureFlags
    metrics: Metrics

    cache: CachePort
    object_store: ObjectStorePort
    chain_store: ChainStorePort
    spool: SpoolPort
    repos: Repositories

    core: CoreBankingPort
    market: MarketDataPort
    news: NewsPort
    crm: CrmPort
    oms: OmsPort

    registry: ToolRegistry
    gateway: ToolGateway
    prompts: PromptLibrary
    classifier: IntentClassifier
    planner: Planner
    generator: Generator
    embedder: Embedder

    suitability: SuitabilityPort
    guardrail: GuardrailPort
    audit: AuditPort
    transactions: TransactionPort

    #: HMAC key for Form Specs (agent-readable, ADR-0009).
    form_signing_key: bytes
    form_signing_key_version: int

    stt: SpeechToTextPort
    tts: TextToSpeechPort
    avatar_vendor: AvatarVendorPort

    checkpointer: Any
    graph: Any = None
    runner: TurnRunner | None = None
    broker: AvatarBroker | None = None
    #: Async callables to run at shutdown (close pools, sessions, tasks).
    closers: list[Any] = field(default_factory=list)

    async def health(self) -> dict[str, bool]:
        """Dependency-aware health surface used by ``/readyz``.

        ``suitability``, ``guardrail`` and ``audit`` are fail-closed: a pod that
        cannot reach them must not receive traffic (docs/04-backend/01 §2).
        """
        import asyncio

        async def probe(name: str, coro: Any) -> tuple[str, bool]:
            try:
                return name, bool(
                    await asyncio.wait_for(coro, timeout=self.settings.services.health_timeout_s)
                )
            except Exception:
                return name, False

        results = await asyncio.gather(
            probe("database", _db_health(self)),
            probe("redis", self.cache.health()),
            probe("object_store", self.object_store.health()),
            probe("suitability", self.suitability.health()),
            probe("guardrail", self.guardrail.health()),
            probe("audit", self.audit.health()),
            probe("transaction", self.transactions.health()),
            probe("core", self.core.health()),
        )
        return dict(results)

    async def aclose(self) -> None:
        for closer in reversed(self.closers):
            try:
                await closer()
            except Exception:
                continue


async def _db_health(deps: Dependencies) -> bool:
    checker = getattr(deps.repos.threads, "health", None)
    if checker is None:
        return True
    return bool(await checker())


#: Set by ``build_dependencies`` (see ``wiring.py``); imported lazily by routes.
_current: Dependencies | None = None


def set_current(deps: Dependencies | None) -> None:
    global _current
    _current = deps


def get_current() -> Dependencies:
    if _current is None:
        raise RuntimeError("dependencies not initialised")
    return _current
