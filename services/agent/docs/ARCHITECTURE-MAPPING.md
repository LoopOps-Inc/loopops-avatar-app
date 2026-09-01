# Traceability: reference documents → code → tests

Paths under `docs/` refer to the sibling repository `actinver-ai-advisor`. Code
paths are relative to `services/agent/src/actinver_agent/`; tests to
`services/agent/tests/`.

## Architecture documents

| Document / section | Requirement | Code | Test |
|---|---|---|---|
| 01-architecture/01 §4 Split-channel rendering | speech narrative, exact figures only in `ui`; composer is the only writer of speech | `graph/nodes/composer.py`, `llm/speech_format.py`, `guardrails/engine.py` (PRECISE_AMOUNT, identifiers) | `graph/test_turns.py::test_portfolio_inspect_split_channel`, `unit/test_guardrails.py` |
| 01-architecture/01 §7 Degradation ladder | vendor/model/core outages degrade, fail-closed controls refuse | `graph/runtime.py` (CORE_UNAVAILABLE), `graph/nodes/agent_core.py` (MODEL_UNAVAILABLE), `graph/nodes/guards.py`, `suitability_node.py`, `audit.py` | `graph/test_turns.py::test_core_outage_refuses_instead_of_serving_stale` |
| 01-architecture/01 §8 Freshness contract | cache TTL = freshness ceiling, never serve stale | `tools/gateway.py` (`_read_cache` ceiling), `ToolSpec.cache_ttl_s` per catalogue | `unit/test_auth_voice_tools.py::test_breaker_*` |
| 01-architecture/01 §9 Identity | `client_id` from the token only, thread per client per channel | `auth/*`, `graph/runtime.py`, `graph/state.py::assert_identity_unchanged`, `graph/builder.py::guarded` | `graph/test_topology.py::test_identity_fields_are_write_once` |
| 01-architecture/03 §5 Transactional flow | planner → FormSpec → interrupt → step-up → executor → resume | `graph/nodes/transaction.py`, `api/routes/forms.py`, `transactions/executor.py`, `graph/runtime.py::resume_form` | `graph/test_turns.py::test_transaction_emits_signed_form_and_suspends`, `api/test_api.py::test_transaction_flow_end_to_end` |
| 01-architecture/04 §3 Persistence layout | schemas session/txn/catalog/rules/audit, RLS, pgvector | `persistence/models.py`, `migrations/versions/0001_initial.py`, `persistence/db.py::identity_scope` | `integration/test_stack.py` |
| 01-architecture/04 §4 Evidence record | one record per turn, documented fields, hash chain, retention | `audit/record.py`, `audit/sink.py` | `unit/test_audit.py` |
| 01-architecture/04 §6 What reaches the model | first name, bands, percentages; redaction proxy on the serialised body | `llm/prompts.py::render_system`, `llm/redaction.py`, `adapters/gemini.py` | `unit/test_auth_voice_tools.py` (patterns), `test_prompts` in graph turns |
| 01-architecture/05 LiveAvatar LITE | token → start → WS `connected` gate → agent.speak 24 kHz PCM ~1 s chunks → stop; agent token never leaves | `clients/liveavatar.py`, `avatar/broker.py`, `voice/framing.py` | `contract/test_liveavatar_contract.py`, `api/test_api.py::test_avatar_session_requires_voice_consent_and_hides_agent_token` |
| 01-architecture/05 §5 Barge-in | interrupt + cancel in-flight run, 1.5 s stutter window | `voice/ws_handler.py`, `avatar/broker.py::ActiveSession.cancel_turn` | `api/test_voice_ws.py` |
| 01-architecture/05 §7 Cost controls | 30 s background, 90/150 s idle, 1800 s cap, semaphore, daily budget, metrics | `avatar/broker.py` (`_watchdog`, `background_grace`, `SLOT_KEY`), `observability/setup.py` metrics | `api/test_voice_ws.py::test_broker_capacity_budget_and_stop` |
| 01-architecture/06 §2 Graph topology | mandatory steps are edges | `graph/builder.py` | `graph/test_topology.py` |
| 01-architecture/06 §3.1 ingress_guard | injection, PII redaction, scope, distress, ASR confidence, no model call | `guardrails/engine.py::check_input`, `graph/nodes/guards.py::ingress_guard` | `unit/test_guardrails.py`, `graph/test_turns.py::test_injection_is_blocked_before_any_model_call` |
| 01-architecture/06 §3.2 intent_router | closed set, advisory bias | `llm/stub.py::RulesIntentClassifier`, `adapters/gemini.py::GeminiClassifier`, `graph/nodes/routing.py` | `unit/test_auth_voice_tools.py::test_router_*` |
| 01-architecture/06 §3.3 entitlement_gate | degradation, expired profile blocks advice | `graph/nodes/routing.py::entitlement_gate` | `graph/test_turns.py::test_advisory_without_contract_degrades_to_generic`, `::test_expired_profile_*` |
| 01-architecture/06 §3.4 plan/tool_execution | ≤4 rounds, ≤10 calls, 3 s/8 s budgets, parallel, provenance, untrusted content scan | `graph/nodes/agent_core.py`, `tools/registry.py::record_provenance` | `unit/test_auth_voice_tools.py::test_record_provenance_*` |
| 01-architecture/06 §3.6 suitability_gate | deterministic, versioned, signed, NO_APTO stripped | `suitability/rules.py`, `engine.py`, `graph/nodes/suitability_node.py` | `unit/test_suitability.py` (100 % replay, monotonicity), `graph/test_turns.py::test_advisory_turn_is_gated_*` |
| 01-architecture/06 §3.7 compliance_guard | claims, disclosures verbatim, provenance, split-channel, REWRITE ≤2 | `guardrails/engine.py::check_output`, `graph/nodes/guards.py::compliance_guard` | `unit/test_guardrails.py` |
| 01-architecture/06 §3.8 transaction_planner | FormSpec shape, 10-min TTL, signature | `transactions/formspec.py`, `graph/nodes/transaction.py` | `unit/test_transactions.py` |
| 01-architecture/06 §4 Prompt architecture | versioned prompt files, verbatim disclosures | `prompts/`, `llm/prompts.py`, `guardrails/disclosures.py` | `assertions/test_disclosures_exact.py` |
| 01-architecture/06 §5 Model routing | Flash informational, Pro advisory/explain/transactional, flag-pinned | `graph/nodes/agent_core.py`, `flags.py` | graph turns (`model_meta`) |
| 04-backend/01 §4 API surface | endpoint table | `api/routes/*` | `api/test_api.py::test_health_and_openapi` |
| 04-backend/02 §1 Enforced rules | mypy strict, ruff S/ASYNC, 80 % floor, no SDK outside adapters, secrets by reference, redaction processor | `pyproject.toml`, `observability/setup.py::_drop_content`, `secrets.py` | `assertions/test_no_sdk_outside_adapters.py`, CI |
| 04-backend/03 Tool catalogue | names, classes, TTLs, Spanish descriptions, INTENT_TOOL_MAP | `tools/*.py` | `assertions/test_registry_no_writes.py` |
| 04-backend/04 API contract | RFC 9457, idempotency, cursor, money, SSE `done` | `errors.py`, `auth/dependencies.py::IdempotencyGuard`, `api/routes/threads.py` | `api/test_api.py` |
| 04-backend/05 Observability | metrics names, no content in spans | `observability/setup.py` | `unit/test_infra.py::test_observability_helpers` |

## ADRs

| ADR | Decision | Where |
|---|---|---|
| 0001 LITE mode | vendor renders only; we own STT/LLM/TTS | `clients/liveavatar.py` (`mode: "LITE"`), `voice/pipeline.py` |
| 0002 Cascaded pipeline | text checkpoint before playback, per-sentence guard | `voice/pipeline.py` (guard `sentence_mode=True` before TTS) |
| 0003 Vertex AI | `LLM_PROVIDER=vertex`; `gemini_api` local-only | `adapters/gemini.py::GeminiClientFactory`, `config.py::validate_posture` |
| 0004 LangGraph | edges not tools, Postgres checkpointer, interrupt | `graph/*`, `graph/checkpointer.py` |
| 0005 Deterministic suitability | engine, key not agent-readable | `suitability/*`, `api/app.py::assert_suitability_key_unreadable`, compose env |
| 0006 Split-channel | linter on speech, ui exact | `guardrails/patterns.py`, `graph/nodes/composer.py` |
| 0008 LiveKit direct | client gets scoped token only | `ports.py::VendorSession.client_payload` |
| 0009 Server-driven forms | signed FormSpec, closed field types, re-derived limits | `graph/state.py::FormSpec`, `transactions/executor.py::_validate_against` |
| 0010 Agent never executes | registry refuses `mutating=True`; executor separate | `tools/registry.py`, `transactions/service.py` |
| 0011 Cloud-agnostic | S3 API, Kafka-free, SDKs under adapters | `adapters/`, `ops/k8s`, `assertions/test_no_sdk_outside_adapters.py` |
| 0012 WORM + chain | object lock, sha256 chain, anchor, spool | `audit/sink.py`, `adapters/s3_store.py` |
| 0013 Spanish first | es-MX texts, lexicon, register consistency | `prompts/system/lexicon.es-MX.yaml`, `guardrails/engine.py::_register_mismatch` |
| 0014 No client data in vectors | indexer classifier, retriever has no client_id | `retrieval/indexer.py`, `retrieval/retriever.py` |
| 0015 Flags + kill switch | inventory, expiry, Redis store, 30 s propagation | `flags.py`, `api/routes/compliance.py`, `api/routes/config.py` |
| 0016 OTel + Langfuse | spans per node, content-free | `observability/setup.py::node_span`, compose profile `langfuse` |
| 0017 DPoP + step-up | proof verification, device binding, ES256 challenge | `auth/dpop.py`, `auth/dependencies.py::_register_device`, `auth/stepup.py`, `transactions/executor.py` |
| 0018 Mexico residency | region settings; documented in DEPLOY | `config.py::ObjectStoreSettings.region`, `docs/DEPLOY.md` |

## Compliance control matrix (06-compliance/06)

| Control | Implementation | Evidence / test |
|---|---|---|
| IS-01 turn classified | `service_type`/`service_subtype` in state and evidence | `graph/test_turns.py` done events |
| IS-02 advisory without contract | `entitlement_gate` degradation + metric `turn.count{event=degradation}` | `test_advisory_without_contract_degrades_to_generic` |
| IS-03 expired profile | R-001 + gate | `test_expired_profile_blocks_advice_and_offers_update` |
| IS-04 razonabilidad on every recommendation | `suitability_gate` mandatory edge; `suitability` in every advisory record | `test_topology`, `test_advisory_turn_is_gated_*`, replay corpus |
| IS-05 incongruent products removed | `stripped_products` + `STRIPPED_PRODUCT_LEAK` guard | `test_advisory_turn_is_gated_*`, `unit/test_guardrails.py::test_stripped_product_leak_blocks` |
| IS-06 diversification limits | R-012 with committee limits read at evaluation time | `unit/test_suitability.py::test_concentration_limit_is_enforced` |
| IS-07 risk profiles from the committee | `ProductProfile` frozen, never model-writable | `graph/nodes/agent_core.py::_resolve_candidates` |
| IS-08 guide delivered before service | `FIRST_TURN_CONSENTS` gate, versioned acknowledgements | `api/test_api.py::test_first_turn_requires_consents` |
| IS-09 five-year retention | `retention` block, Object Lock `retain_until` | `unit/test_audit.py` |
| IS-10 voice authorisation | `VOICE_RECORDING` consent gate; audio segments carry `consent_version` | `api/test_api.py::test_avatar_session_requires_voice_consent_*` |
| IS-12 fees disclosed | `COSTS` injected on advisory/transactional intents; fee fields in FormSpec | `disclosures_shown` assertions |
| IS-13 no guaranteed returns | `GUARANTEED_RETURN` rule | `unit/test_guardrails.py` |
| IS-14 generic not personalised | degradation notice + `NOT_A_RECOMMENDATION` | `test_advisory_without_contract_degrades_to_generic` |
| DP-01/02/03 consents | `ConsentType` records, versions, model-improvement default off | `assertions/test_model_improvement_default_off.py`, `api/test_api.py::test_consent_roundtrip` |
| DP-04 transfers minimised | redaction proxy, split-channel, DLP export from one source | `guardrails/dlp.py`, `unit/test_guardrails.py::test_dlp_ruleset_*` |
| DP-05 ARCO | `POST /v1/compliance/arco`, request log with timestamps | `api/test_api.py::test_arco_export` |
| DP-06 retention jobs | `persistence/retention.py`, `cli retention` | integration |
| DP-07 human review | `escalation_offer` on every refusal | `test_every_refusal_offers_escalation` |
| AI-01 pinned versions | `model_meta` in evidence, flags for model/prompt/ruleset | evidence record tests |
| AI-02 deterministic suitability | 100 % replay gate | `test_replay_corpus_matches_100_percent` |
| AI-03 provenance | `record_provenance` + guard + composer invariant | `test_unsourced_figure_is_caught_and_sourced_passes` |
| AI-04 every utterance filtered | turn-level + per-sentence guard before TTS | `voice/pipeline.py`, `api/test_voice_ws.py` |
| AI-05 no execution tool | registry assertion | `assertions/test_registry_no_writes.py`, `test_no_tool_in_registry_mutates` |
| AI-06 no model-supplied client id | registry strips and logs | `tools/registry.py::call` |
| AI-07 no precise data in voice | split-channel linter + DLP | guardrail tests |
| AI-08 no client data in corpus | indexer rejection test | `test_indexer_rejects_client_identifiers` |
| AI-09 AI disclosure | `AI_ASSISTANT` first-turn consent + advisory disclosure | session/consent tests |
| AI-10 kill switch < 30 s | Redis-backed flag, `/v1/config` poll 30 s | `test_flag_authority_and_kill_switch`, `test_kill_switch_returns_static_message_without_model` |
| EV-01 one record per turn | `audit_sink` on every path | `test_every_terminal_path_ends_in_audit_sink` |
| EV-02 hash chain | `EvidenceWriter` | `test_chain_links_records_per_thread`, `test_tampering_is_detected_by_verify_chain` |
| EV-03 anchoring | `anchor_heads` to the anchor bucket | `test_legal_hold_and_anchor` |
| EV-04 WORM no bypass | Object Lock + no delete path in adapter | `test_worm_objects_cannot_be_overwritten` |
| EV-05 evidence access logged | `access_log` on every compliance read | `test_compliance_requires_role_and_reason` |
| EV-07 reconstructible in minutes | indexed retrieval by client/thread/turn/date/service/product | `test_evidence_index_query_filters` |

## Threat model (05-security/02) mitigations in code

| Scenario | Barrier(s) |
|---|---|
| §4.1 injection to read another client | detector blocks before model (`ingress_guard`); registry strips `client_id` and logs; write-once state; RLS bound to identity |
| §4.2 hostile retrieved content | `<contenido_externo>` framing in prompts, `scan_retrieved` drops hits, citation enforcement, `compliance_guard` |
| §4.3 guaranteed-return leak | per-sentence guard before synthesis |
| §4.4 evidence tampering | object lock, chain, anchor in a separate bucket/credentials |
| §4.5 forged APTO | HMAC key only in `suitability` process; agent startup assertion |
| §4.6 vendor compromise | flags `advisor.avatar`/`advisor.voice_mode`; chat continues; deterministic model fallback (`LLM_PROVIDER=stub`) |
