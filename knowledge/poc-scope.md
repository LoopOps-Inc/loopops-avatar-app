# POC Scope

**Status:** Active · **Branch:** `poc/structure`

This document defines what we build now versus what the BA reference architecture
(`actinver-ai-advisor`) describes for production.

## POC goal

> Chat-mode advisor that answers portfolio and market questions with streamed text
> and rich cards, backed by a LangGraph agent with mock tools. Avatar lip-sync
> comes later on the existing HeyGen sandbox demo.

## Ownership

| Area                   | Owner        | Status                                                                  |
| ---------------------- | ------------ | ----------------------------------------------------------------------- |
| API contract           | Shared       | Done — `packages/contracts`                                             |
| Backend (`apps/agent`) | Backend dev  | **Not started** — see [`apps/agent/README.md`](../apps/agent/README.md) |
| Frontend (`apps/web`)  | Frontend dev | `/advisor` + mock domain data in `apps/web/src/mocks/`                  |
| HeyGen sandbox         | Frontend dev | Done at `/demo`                                                         |

## In scope

| Area          | POC deliverable                                                    |
| ------------- | ------------------------------------------------------------------ |
| Contract      | Frozen v0 shapes in `packages/contracts` (TypeScript + Zod)        |
| Backend       | FastAPI + LangGraph: sessions, chat SSE, mock tools (backend team) |
| Split-channel | `speech` (narrative) + `ui_payload[]` (exact figures)              |
| Frontend      | `/advisor` route with `UIPayloadRenderer` (after API lands)        |
| Agent         | LangGraph: intent routing → tools → composer (backend team)        |

## Out of scope (target-state only)

- Microservice split, network zoning, WORM audit, DPoP auth
- Suitability engine, transactions, Form Spec
- Real Actinver core APIs
- LiveAvatar LITE in the advisor flow (keep `/demo` sandbox separate)

## Monorepo layout

```
├── apps/
│   ├── web/               # Vite + React frontend
│   └── agent/             # Python BFF — instructions only until backend team ships
├── packages/
│   └── contracts/         # Shared API contract (TypeScript + Zod)
└── knowledge/             # Architecture docs
```

## API contract v0

See `packages/contracts` and `apps/agent/README.md` for full detail.

| Endpoint                         | Purpose                                                |
| -------------------------------- | ------------------------------------------------------ |
| `POST /v1/sessions`              | Returns `thread_id`, `capabilities`, disclosures       |
| `POST /v1/threads/{id}/messages` | Chat message; SSE (`token`, `ui`, `citations`, `done`) |
| `GET /healthz`                   | Liveness                                               |

## Cross-references

- [`apps/agent/README.md`](../apps/agent/README.md) — backend implementation handoff
- [`apps/agent/AGENTS.md`](../apps/agent/AGENTS.md) — agent instructions for backend
- [`packages/contracts/README.md`](../packages/contracts/README.md) — contract source of truth
- BA phasing: chat (Phase 1) before avatar (Phase 2)
