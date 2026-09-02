# services/agent — Actinver AI Advisor backend

Python 3.12 · FastAPI · LangGraph · Gemini (Vertex AI) · PostgreSQL 16 + pgvector · Redis 7 · S3 WORM (floci locally) · HeyGen LiveAvatar LITE

This service implements the backend described by the reference architecture in the
sibling repository `actinver-ai-advisor` (`docs/` and `services/agent/`). Every
compliance control in those documents is code here: the suitability gate is a
deterministic, signed rules engine; every utterance passes an output guardrail
before it can be spoken; the agent never executes a transaction; every turn
produces one hash-chained evidence record on WORM storage. The web frontend in
`apps/web` consumes the API documented in [`docs/API.md`](docs/API.md).

## What runs where

The architecture names nine logical services. Locally (and in `ops/k8s`) they are
one image and five processes, chosen so that the controls that must not share a
process with the agent do not:

| Process (`serve --role`) | Logical services it contains                                                | Why separate                                                                                                |
| ------------------------ | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `agent`                  | bff-mobile, agent-orchestrator, avatar-broker, voice-pipeline, tool-gateway | The product surface. Session-affine only for the avatar WebSocket.                                          |
| `suitability`            | suitability-service                                                         | Owns the verdict HMAC key. The agent process cannot read it (startup assertion). Compliance owns the rules. |
| `guardrail`              | guardrail-service                                                           | Fail-closed input/output filters; policy changes independently of the agent.                                |
| `audit`                  | audit-service                                                               | WORM evidence writer, hash chain, spool, anchor. Must survive the agent failing.                            |
| `transaction`            | transaction-service                                                         | Step-up verification, independent re-validation, idempotent execution. The agent is untrusted input to it.  |

Backing services: PostgreSQL 16 with pgvector (checkpoints, sessions, forms, rules,
audit index, retrieval), Redis 7 (cache at the freshness ceilings, rate limits,
avatar concurrency semaphore, flags), an S3-compatible object store with Object
Lock (evidence, transcripts, audio, form-spec copies, ARCO exports) and a Secrets
Manager. Locally both AWS services are emulated by [floci](https://floci.io/aws/).

```
src/actinver_agent/
├── api/            FastAPI app + routes (sessions, threads/SSE, forms, avatar+WS, consents,
│                   config, telemetry, compliance console)       docs/04-backend/04
├── auth/           JWT (dev HS256 / OIDC JWKS), DPoP (RFC 9449), step-up ES256, rate limits
├── graph/          LangGraph state, nodes, topology, TurnRunner   docs/01-architecture/06
├── tools/          Tool registry + gateway (cache, breakers, provenance) docs/04-backend/03
├── llm/            Prompt library, redaction proxy, deterministic stub model
├── adapters/       Provider SDKs ONLY here: google-genai, Google STT/TTS, S3, Secrets Manager, Redis
├── clients/        Synthetic core (demo data), contract-first HTTP clients, LiveAvatar LITE client
├── suitability/    Rules engine v14, signing, replay corpus, service + client
├── guardrails/     patterns.py (single source), engine, disclosures, DLP export, service + client
├── audit/          Evidence record, writer (chain, WORM, spool, anchor), service + client
├── transactions/   FormSpec signing, executor, typed errors, service + client
├── avatar/         Broker (semaphore, budgets, timers), filler bank, emulated vendor
├── voice/          Sentence splitter, PCM framer, pipeline, audio WebSocket handler, stubs
├── retrieval/      Indexer with client-data rejection, retriever, seed corpus (no client data)
├── persistence/    SQLAlchemy models + repositories with RLS identity, memory doubles, retention
└── observability/  OTel + structlog with structural content redaction
```

## What is real and what is a stub

| Component                                  | Default (local/CI)                                                                                                                                                                                                    | Production binding                                                                                                                                        |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model                                      | `LLM_PROVIDER=stub` — deterministic templated es-MX generator, rules-based router. Also the documented fallback when the model provider is down.                                                                      | `LLM_PROVIDER=vertex` (Gemini 2.5 Flash/Pro via `google-genai`, workload identity). `gemini_api` (AI Studio key) is accepted in `ENVIRONMENT=local` only. |
| Core banking / market / news / CRM / OMS   | `CORE_PROVIDER=synthetic` — deterministic demo clients and catalogue, fault injection for outage tests                                                                                                                | `CORE_PROVIDER=http` — contract-first mTLS clients in `clients/*_http.py`, pending the core API inventory                                                 |
| Avatar vendor                              | `LIVEAVATAR_PROVIDER=stub` — emulated LITE session and control channel                                                                                                                                                | `LIVEAVATAR_PROVIDER=real` — `clients/liveavatar.py` (sandbox or production)                                                                              |
| Voice                                      | `VOICE_PROVIDER=stub` — text transcripts via the dev-only `dev.transcript` WS message, silent PCM. `gemini_api` adds AI Studio TTS and utterance-level STT (one Gemini call per `utterance_end`, no interim results). | `VOICE_PROVIDER=google` — streaming STT + 24 kHz TTS                                                                                                      |
| Object store / secrets                     | floci (S3 Object Lock, Secrets Manager)                                                                                                                                                                               | AWS or any S3-compatible store; External Secrets Operator                                                                                                 |
| Suitability, guardrail, audit, transaction | Separate containers over HTTP (`SVC_*_URL`), or `inprocess` for tests                                                                                                                                                 | Separate deployments, separate key material                                                                                                               |

## Quickstart (Docker)

```sh
cd services/agent
cp .env.example .env                    # optional: every value has a local default
docker compose up -d --build            # postgres, redis, floci(+init), otel, migrate, 5 services
docker compose logs -f agent            # wait for "startup.complete"
make token CLIENT=cl_demo_moderado      # prints an export line with a dev access token
make smoke                              # step-by-step end-to-end run (see docs/API.md)
```

Swagger UI: <http://localhost:8443/docs> · OpenAPI 3.1: <http://localhost:8443/openapi.json>
(also exported to `docs/openapi/*.json` for every role).

Host ports: agent `8443`; Postgres `15432`, Redis `16379`, floci `14566`, OTLP `14317`
(all overridable via `*_HOST_PORT` to avoid clashing with local installs).

### Demo clients (synthetic core)

| `client_id`           | Name  | Profile                    | Contracts            | Use it to see                                                      |
| --------------------- | ----- | -------------------------- | -------------------- | ------------------------------------------------------------------ |
| `cl_demo_moderado`    | José  | moderado, 24 m, intermedio | advisory + execution | full advisory path, suitability stripping, transactions            |
| `cl_demo_conservador` | Ana   | conservador                | execution only       | advisory degrades to generic discovery with `NOT_A_RECOMMENDATION` |
| `cl_demo_agresivo`    | Luis  | agresivo, avanzado         | advisory + execution | high-risk products APTO, simulations                               |
| `cl_demo_vencido`     | Marta | moderado, profile expired  | advisory + execution | `PROFILE_EXPIRED` refusal + profile-update offer                   |

Products: `ACTIGOB-BF` (bajo), `ACTICETES-BF` (bajo), `ACTICORP-BF` (medio), `ACTIMIX-BF`
(medio), `ACTIUSD-BF` (bajo, USD), `ACTIVAR-RV` (alto), `ACTIGLOB-RV` (alto), `ACTIREAL-BF` (alto).

## Local development without Docker (agent only)

```sh
uv venv --python 3.12 .venv && uv pip install -e '.[dev]'
export $(grep -v '^#' .env.example | xargs)   # or write your own .env
# in-process posture: everything in memory, no infra needed
ENVIRONMENT=local CACHE_PROVIDER=memory CHECKPOINTER_PROVIDER=memory OBJECT_STORE_PROVIDER=memory \
SECRETS_MANAGER_ENDPOINT= AUTH_DEV_SIGNING_KEY=dev CLIENT_HASH_SALT=salt \
.venv/bin/python -m actinver_agent.cli serve --role agent --port 8443
```

## Testing

```sh
make lint        # ruff (S bandit + ASYNC rules)
make typecheck   # mypy --strict
make test        # unit + graph topology + API + contract + build-time assertions, 80 % floor
make test-integration   # AGENT_BASE_URL=http://localhost:8443 against the compose stack
```

Suites that encode the architecture: `tests/graph/test_topology.py` (no path from
`agent_core` to the composer bypasses `compliance_guard`; every path ends in
`audit_sink`; no tool mutates), `tests/unit/test_suitability.py` (100 % replay
gate, Hypothesis monotonicity), `tests/unit/test_guardrails.py` (adversarial
corpora, split-channel, provenance), `tests/assertions/` (no SDK outside
`adapters/`, flags unexpired, exact disclosure strings, no vendor secrets in
`apps/web/src`, UI component types closed).

## Real vendor keys locally (Gemini, LiveAvatar)

Everything runs offline by default (`LLM_PROVIDER=stub`, `LIVEAVATAR_PROVIDER=stub`,
`VOICE_PROVIDER=stub`). To test against the real vendors from your machine:

```sh
cp .env.example .env          # Compose reads this file automatically
# edit .env:
#   GEMINI_API_KEY=<AI Studio key>
#   LIVEAVATAR_API_KEY=<HeyGen sandbox key>
#   LIVEAVATAR_PROVIDER=real
docker compose up -d floci-init                          # seeds the keys into the local Secrets Manager
docker compose --profile gemini up -d agent-gemini        # real Gemini on http://localhost:8444
.venv/bin/python scripts/postman_env.py --base-url http://localhost:8444
```

The processes never see the key values: `.env` is read by Compose, `floci-init`
stores the keys in the emulated Secrets Manager, and the services resolve the
`secretsmanager://` references at start-up, exactly as in the cloud. The stub
`agent` on :8443 keeps running; use :8444 for the real model
(`BASE_URL=http://localhost:8444 make postman-check` runs the whole collection
against it). Sandbox/trial LiveAvatar accounts cap `max_session_duration` well
below the contracted 1800 s; the broker reads the cap from the vendor's 400 and
retries once with it, so the session still starts. `gemini_api` is
accepted only with `ENVIRONMENT=local`; every other environment uses Vertex AI
with workload identity. `VOICE_PROVIDER=google` additionally needs a Google
service account mounted into the container
(`GOOGLE_APPLICATION_CREDENTIALS_IN_CONTAINER`).

## Testing by hand (Postman)

`docs/postman/actinver-agent.postman_collection.json` walks the full client flow
(health, session, consents, SSE turns, transaction form, step-up, avatar, config,
compliance console). Each request's test script saves the ids the next request
needs (`thread_id`, consent versions, `form_id`, `challenge_id`, ...).

```sh
make postman          # writes docs/postman/local.postman_environment.json (tokens, device JWK)
make postman-check    # same flow headless with Newman, signature included
```

Import the collection and the generated environment in Postman, select the
environment and send the requests top to bottom. The only manual step is 5.2: sign
the challenge printed in the Postman console
(`.venv/bin/python scripts/dev_token.py --sign-challenge <challenge> --quiet`) and
paste the output into the environment variable `assertion`. Tokens live 15 minutes:
re-run `make postman` and re-import the environment when they expire.

## Configuration

Every value is environment-driven and validated at startup (`config.py`). The
environment carries secret **references** (`secretsmanager://`, `kms://`,
`file://`, `env://` local-only), never values; a startup assertion fails the
process if a reference field looks like a secret. `Settings.validate_posture()`
refuses local-only bindings (`gemini_api`, dev auth, optional DPoP, memory
stores, GOVERNANCE lock mode in prod) outside `ENVIRONMENT=local`. See
`.env.example` for the full table.

## Deployment

Kubernetes manifests (Kustomize) live in `ops/k8s`; see [`docs/DEPLOY.md`](docs/DEPLOY.md).
Migrations run as an init job (`cli migrate`), forward-only. Secrets come from the
External Secrets Operator. The suitability HMAC key is mounted into the
suitability deployment only.

## Documentation

- [`docs/API.md`](docs/API.md) — every endpoint the frontend needs, step by step with curls, SSE/WS catalogues, error codes.
- [`docs/ARCHITECTURE-MAPPING.md`](docs/ARCHITECTURE-MAPPING.md) — traceability from the reference docs, ADRs and control IDs to modules and tests.
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — environments, posture per environment, rollout and kill switch.
- `docs/openapi/` — exported OpenAPI 3.1 for the agent and the four control services.

## Deviations from the reference documents (and why)

| Topic                        | Documents say                                                           | Here                                                                                                                                                                                                                                                                                                                   | Why                                                                                                                                     |
| ---------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime base image           | distroless `python3-debian12`                                           | `python:3.12-slim` non-root, read-only rootfs, no pip                                                                                                                                                                                                                                                                  | The distroless image ships Python 3.11; the service pins 3.12. Swap to a 3.12 distroless base when available (comment in `Dockerfile`). |
| Transcripts                  | one `transcripts/{y}/{m}/{thread}.jsonl`                                | one object per turn under the thread prefix                                                                                                                                                                                                                                                                            | S3 objects are immutable under Object Lock; appending is not possible.                                                                  |
| DPoP                         | required everywhere                                                     | required outside `local`; optional (verified when present) in `local`                                                                                                                                                                                                                                                  | plain curls for developers. `AUTH_DPOP_REQUIRED=true` restores the strict posture.                                                      |
| Checkpoint partitioning      | monthly partitions                                                      | DDL provided in `ops/sql/checkpoint_partitioning.sql` as a DBA runbook                                                                                                                                                                                                                                                 | LangGraph creates its tables itself; partitioning is a deployment-time operation.                                                       |
| Object Lock                  | AWS compliance mode                                                     | floci emulation locally; `OBJECT_STORE_LOCK_MODE=GOVERNANCE` in local/staging, `COMPLIANCE` enforced in prod by posture validation                                                                                                                                                                                     | records written in error must be recoverable outside production (ADR-0012).                                                             |
| Legal texts                  | legal-approved                                                          | `api/disclosure_docs.py` placeholders marked for Legal approval; disclosure texts from the reference `disclosures.es-MX.md`                                                                                                                                                                                            | Legal sign-off is an `[ACTINVER-INPUT]` item in the docs.                                                                               |
| Structured plan completeness | model plans the full tool set and emits `<candidatos>`/`<monto>` blocks | the graph enforces it: `mode=ANY` returns a single call and a real model does not always emit the blocks, so the graph structurally forces `get_transaction_requirements`/`check_suitability`/`search_investment_products` and falls back to tool results and the client's stated amount (`graph/nodes/agent_core.py`) | the compliance flow must not depend on model prose compliance; the deterministic gates (suitability, guardrail, audit) still decide.    |
| LiveAvatar session length    | `max_session_duration` 1800 s                                           | the broker honours the vendor's cap when a sandbox/trial account rejects 1800 s (retries once with the cap)                                                                                                                                                                                                            | sandbox accounts cap sessions at 60 s; the session must still start (`clients/liveavatar.py`).                                          |
