"""Build the ``Dependencies`` object for a given role and configuration.

This is the only module that knows every concrete adapter. Provider choices
are driven by ``Settings`` (see ``deps.py`` docstring). Fail-closed controls
(suitability, guardrail, audit, transaction) are either in-process libraries
or HTTP clients to the separately deployed services; the graph never knows
which.
"""

from __future__ import annotations

import contextlib
import secrets as pysecrets
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import structlog

from actinver_agent.config import Settings
from actinver_agent.deps import Dependencies
from actinver_agent.flags import FeatureFlags
from actinver_agent.observability.setup import get_metrics, set_client_hash_salt
from actinver_agent.persistence.wiring import (
    build_cache,
    build_object_store,
    build_resolver,
    build_sql_backends,
)
from actinver_agent.secrets import SecretResolutionError, SecretResolver

log = structlog.get_logger(__name__)

Closer = Callable[[], Awaitable[None]]


async def _resolve_or_local_default(
    resolver: SecretResolver, settings: Settings, reference: str, *, name: str
) -> str:
    """Resolve a secret; in local, fall back to a generated per-process value so
    the stack boots without seeding. Never in dev/staging/prod."""
    try:
        return await resolver.resolve(reference)
    except SecretResolutionError:
        if not settings.is_local:
            raise
        log.warning("secrets.local_fallback", secret=name)
        return pysecrets.token_hex(32)


async def build_dependencies(settings: Settings) -> Dependencies:
    metrics = get_metrics()
    resolver = build_resolver(settings)
    closers: list[Closer] = []

    salt = await _resolve_or_local_default(
        resolver, settings, settings.client_hash_salt_ref, name="client_hash_salt"
    )
    set_client_hash_salt(salt.encode())

    cache, cache_closer = await build_cache(settings)
    if cache_closer is not None:
        closers.append(cache_closer)
    flags = FeatureFlags(cache)

    object_store = await build_object_store(settings, resolver)
    anchor_store = await build_object_store(
        settings, resolver, bucket=f"{settings.object_store.bucket}-anchor"
    )

    sql = build_sql_backends(settings, service_identity=f"{settings.service_role}_svc")
    closers.extend(sql.closers)
    repos, chain_store, spool = sql.repos, sql.chain, sql.spool
    if settings.service_role == "agent" and sql.sessions is not None:
        # The compliance console reads evidence across clients. Row-level security
        # scopes agent_svc to the calling client, so those reads run under the
        # read-only compliance identity (docs/05-security/03 §4, EV-05 logging applies).
        from actinver_agent.persistence.repositories import SqlEvidenceIndexRepository

        repos.evidence_index = SqlEvidenceIndexRepository(
            sql.sessions, service_identity="compliance_ro"
        )

    # ── core systems (through tool-gateway) ──────────────────────────────────
    if settings.core_provider == "synthetic":
        from actinver_agent.clients.synthetic import (
            SyntheticCoreBanking,
            SyntheticCrm,
            SyntheticMarketData,
            SyntheticNews,
            SyntheticOms,
        )

        core: Any = SyntheticCoreBanking()
        market: Any = SyntheticMarketData()
        news: Any = SyntheticNews()
        crm: Any = SyntheticCrm()
        oms: Any = SyntheticOms()
    else:  # pragma: no cover - needs the core API inventory
        from actinver_agent.clients.core_http import CoreBankingHttp
        from actinver_agent.clients.crm_http import CrmHttp
        from actinver_agent.clients.market_http import MarketDataHttp
        from actinver_agent.clients.news_http import NewsHttp
        from actinver_agent.clients.oms_http import OmsHttp

        market_key = await resolver.try_resolve(settings.market_data_api_key_ref)
        core = CoreBankingHttp(settings)
        market = MarketDataHttp(settings, api_key=market_key)
        news = NewsHttp(
            settings,
            search_base_url=settings.news_search_base_url,
            research_base_url=settings.research_base_url,
        )
        crm = CrmHttp(settings, base_url=settings.crm_base_url)
        oms = OmsHttp(settings, base_url=settings.oms_base_url)
        for client in (core, market, news, crm, oms):
            closer = getattr(client, "aclose", None)
            if closer is not None:
                closers.append(closer)

    # ── fail-closed controls ─────────────────────────────────────────────────
    internal_http = httpx.AsyncClient(timeout=settings.services.request_timeout_s)
    closers.append(internal_http.aclose)

    form_key = (
        await _resolve_or_local_default(
            resolver, settings, settings.form_spec_signing_key_ref, name="formspec_hmac"
        )
    ).encode()

    if settings.services.guardrail_url == "inprocess":
        from actinver_agent.guardrails.inprocess import InProcessGuardrail

        guardrail: Any = InProcessGuardrail(
            prompts_dir=settings.prompts_dir, min_confidence=settings.voice.stt_min_confidence
        )
    else:
        from actinver_agent.guardrails.client import HttpGuardrail

        guardrail = HttpGuardrail(
            settings.services.guardrail_url,
            internal_http,
            timeout_s=settings.services.request_timeout_s,
        )

    if settings.services.suitability_url == "inprocess":
        from actinver_agent.suitability.inprocess import InProcessSuitability

        suit_key = (
            await _resolve_or_local_default(
                resolver, settings, settings.suitability_signing_key_ref, name="suitability_hmac"
            )
        ).encode()
        suitability: Any = InProcessSuitability.with_key(
            suit_key, ruleset_version=settings.suitability_ruleset_version
        )
    else:
        from actinver_agent.suitability.client import HttpSuitability

        suitability = HttpSuitability(
            settings.services.suitability_url,
            internal_http,
            timeout_s=settings.services.request_timeout_s,
        )

    if settings.services.audit_url == "inprocess":
        from actinver_agent.audit.inprocess import InProcessAudit
        from actinver_agent.audit.sink import EvidenceWriter

        writer = EvidenceWriter(
            store=object_store,
            chain=chain_store,
            index=repos.evidence_index,
            spool=spool,
            lock_mode=settings.object_store.lock_mode,
            retention_years=settings.object_store.retention_years,
        )
        audit: Any = InProcessAudit(writer)
    else:
        from actinver_agent.audit.client import HttpAudit

        audit = HttpAudit(
            settings.services.audit_url,
            internal_http,
            timeout_s=max(settings.services.request_timeout_s, 3.0),
        )

    if settings.services.transaction_url == "inprocess":
        from actinver_agent.transactions.executor import TransactionExecutor
        from actinver_agent.transactions.inprocess import InProcessTransactions

        executor = TransactionExecutor(
            core=core,
            oms=oms,
            form_specs=repos.form_specs,
            idempotency=repos.idempotency,
            challenges=repos.challenges,
            devices=repos.devices,
            audit=audit,
            form_key=form_key,
            form_key_version=1,
            challenge_ttl_s=settings.limits.step_up_challenge_ttl_s,
            idempotency_ttl_s=settings.limits.idempotency_ttl_s,
        )
        transactions: Any = InProcessTransactions(executor)
    else:
        from actinver_agent.transactions.client import HttpTransactions

        transactions = HttpTransactions(
            settings.services.transaction_url,
            internal_http,
            timeout_s=max(settings.services.request_timeout_s, 5.0),
        )

    # ── model bindings ───────────────────────────────────────────────────────
    from actinver_agent.llm.prompts import PromptLibrary

    prompts = PromptLibrary(settings.prompts_dir)
    if settings.llm.provider == "stub":
        from actinver_agent.llm.stub import (
            IntentPlanner,
            RulesIntentClassifier,
            StubEmbedder,
            TemplateGenerator,
        )

        classifier: Any = RulesIntentClassifier()
        planner: Any = IntentPlanner()
        generator: Any = TemplateGenerator()
        embedder: Any = StubEmbedder()
    else:
        from actinver_agent.adapters.gemini import (
            GeminiClassifier,
            GeminiClientFactory,
            GeminiEmbedder,
            GeminiGenerator,
            GeminiPlanner,
        )

        api_key = None
        if settings.llm.provider == "gemini_api":
            api_key = await resolver.resolve(settings.llm.gemini_api_key_ref)
        factory = GeminiClientFactory(settings, api_key=api_key)
        classifier = GeminiClassifier(factory, settings, prompts.router_prompt)
        planner = GeminiPlanner(factory, settings, prompts.task_prompt("portfolio_inspect"))
        generator = GeminiGenerator(factory, settings)
        embedder = GeminiEmbedder(factory)

    # ── retrieval + tools ────────────────────────────────────────────────────
    from actinver_agent.retrieval.retriever import MemoryVectorStore, PgVectorStore, Retriever
    from actinver_agent.tools.catalog import build_registry
    from actinver_agent.tools.gateway import ToolGateway

    if settings.checkpointer_provider == "postgres":
        from actinver_agent.persistence.db import create_engine, create_session_factory

        vector_engine = create_engine(settings.database_url)
        vector_store: Any = PgVectorStore(create_session_factory(vector_engine))
        closers.append(vector_engine.dispose)
    else:
        vector_store = MemoryVectorStore()
    retriever = Retriever(embedder, vector_store)
    registry = build_registry(core, market, news, crm, suitability, retriever=retriever)
    gateway = ToolGateway(registry, cache, metrics)

    # ── voice + avatar ───────────────────────────────────────────────────────
    if settings.voice.provider == "google":  # pragma: no cover - needs GCP credentials
        from actinver_agent.adapters.google_speech import GoogleSpeechToText
        from actinver_agent.adapters.google_tts import GoogleTextToSpeech

        stt: Any = GoogleSpeechToText(
            project_id=settings.vertex.project_id,
            language=settings.voice.stt_language,
            model=settings.voice.stt_model,
            phrase_hints=settings.voice.stt_phrase_hints,
            sample_rate_hz=settings.voice.stt_sample_rate_hz,
        )
        tts: Any = GoogleTextToSpeech(
            voice_name=settings.voice.tts_voice_name,
            language_code=settings.voice.stt_language,
            speaking_rate=settings.voice.tts_speaking_rate,
            sample_rate_hz=settings.voice.tts_sample_rate_hz,
        )
    elif settings.voice.provider == "gemini_api":
        # Local-only speech bridge: real synthesis with the AI Studio key,
        # transcription stays on the dev-only text path (ADR-0003).
        from actinver_agent.adapters.gemini import GeminiClientFactory, GeminiTextToSpeech
        from actinver_agent.voice.stub import StubSpeechToText

        voice_key = (
            await resolver.resolve(settings.llm.gemini_api_key_ref)
            if settings.llm.gemini_api_key_ref
            else None
        )
        voice_factory = GeminiClientFactory(settings, api_key=voice_key)
        stt = StubSpeechToText()
        tts = GeminiTextToSpeech(voice_factory, settings)
    else:
        from actinver_agent.voice.stub import StubSpeechToText, StubTextToSpeech

        stt = StubSpeechToText()
        tts = StubTextToSpeech()

    if settings.avatar.provider == "real":  # pragma: no cover - needs a vendor key
        from actinver_agent.clients.liveavatar import LiveAvatarVendor

        api_key_value = await resolver.resolve(settings.avatar.api_key_ref)
        vendor_http = httpx.AsyncClient(timeout=10.0)
        closers.append(vendor_http.aclose)
        avatar_vendor: Any = LiveAvatarVendor(
            settings.avatar, api_key=api_key_value, http=vendor_http
        )
    else:
        from actinver_agent.avatar.stub_vendor import StubAvatarVendor

        avatar_vendor = StubAvatarVendor(
            max_session_duration_s=settings.avatar.max_session_duration_s
        )

    # ── graph ────────────────────────────────────────────────────────────────
    from actinver_agent.graph.checkpointer import make_checkpointer

    checkpointer, checkpointer_closer = await make_checkpointer(settings)
    if checkpointer_closer is not None:
        closers.append(checkpointer_closer)

    deps = Dependencies(
        settings=settings,
        secrets=resolver,
        flags=flags,
        metrics=metrics,
        cache=cache,
        object_store=object_store,
        chain_store=chain_store,
        spool=spool,
        repos=repos,
        core=core,
        market=market,
        news=news,
        crm=crm,
        oms=oms,
        registry=registry,
        gateway=gateway,
        prompts=prompts,
        classifier=classifier,
        planner=planner,
        generator=generator,
        embedder=embedder,
        suitability=suitability,
        guardrail=guardrail,
        audit=audit,
        transactions=transactions,
        form_signing_key=form_key,
        form_signing_key_version=1,
        stt=stt,
        tts=tts,
        avatar_vendor=avatar_vendor,
        checkpointer=checkpointer,
        closers=list(closers),
    )
    # Non-port extras used by CLI jobs.
    deps.anchor_store = anchor_store  # type: ignore[attr-defined]
    deps.retriever = retriever  # type: ignore[attr-defined]

    if settings.service_role == "agent":
        from actinver_agent.avatar.broker import AvatarBroker
        from actinver_agent.avatar.fillers import FillerBank
        from actinver_agent.graph.builder import build_graph
        from actinver_agent.graph.runtime import TurnRunner

        deps.graph = build_graph(deps, checkpointer)
        deps.runner = TurnRunner(deps)
        fillers = FillerBank(tts=tts, cache=cache, voice_id=settings.voice.tts_voice_name)
        with contextlib.suppress(Exception):
            await fillers.warm()
        deps.broker = AvatarBroker(deps, fillers=fillers)

    log.info(
        "wiring.complete",
        role=settings.service_role,
        llm=settings.llm.provider,
        core=settings.core_provider,
        voice=settings.voice.provider,
        avatar=settings.avatar.provider,
        suitability="inprocess" if settings.services.suitability_url == "inprocess" else "http",
        guardrail="inprocess" if settings.services.guardrail_url == "inprocess" else "http",
        audit="inprocess" if settings.services.audit_url == "inprocess" else "http",
        transaction="inprocess" if settings.services.transaction_url == "inprocess" else "http",
    )
    return deps
