# POC Scope

**Status:** Active · **Branch:** `poc/structure`

This document defines what we build now versus what the BA reference architecture
(`actinver-ai-advisor`) describes for production.

## POC goal

> A unified advisor screen where users chat with the Actinver agent (streamed text
> and rich cards) and can turn a talking avatar on or off on the **same thread**.
> HeyGen integration is validated in a separate `/demo` sandbox; the product route
> is `/advisor` (embeddable via `?embed=1`).

See [unified-advisor-avatar.md](./unified-advisor-avatar.md) for the full decision and phasing.

## Ownership

| Area                   | Owner        | Status                                                                  |
| ---------------------- | ------------ | ----------------------------------------------------------------------- |
| API contract           | Shared       | Done — `packages/contracts`                                             |
| Backend (`apps/agent`) | Backend dev  | **Not started** — see [`apps/agent/README.md`](../apps/agent/README.md) |
| Frontend (`apps/web`)  | Frontend dev | `/advisor` unified UI + mock domain data                                |
| HeyGen sandbox         | Frontend dev | Done at `/demo` (internal only)                                         |

## In scope

| Area          | POC deliverable                                                    |
| ------------- | ------------------------------------------------------------------ |
| Contract      | Frozen v0 shapes in `packages/contracts` (TypeScript + Zod)        |
| Backend       | FastAPI + LangGraph: sessions, chat SSE, mock tools (backend team) |
| Split-channel | `speech` (narrative) + `ui_payload[]` (exact figures)              |
| Frontend      | `/advisor` unified screen: chat, cards, avatar toggle, embed mode  |
| Agent         | LangGraph: intent routing → tools → composer (backend team)        |
| Avatar UI     | Mobile full-viewport layout; sandbox video in Phase 2a             |
| Avatar speech | Agent `speech` → avatar broker → LITE lip-sync in Phase 2b         |

## Out of scope (target-state only)

- Microservice split, network zoning, WORM audit, DPoP auth
- Suitability engine, transactions, Form Spec
- Real Actinver core APIs
- End-user traffic on `/demo` (sandbox dev route only)
- Full voice mode (mic → STT) before Phase 3

## POC phasing

| Phase                  | Focus                                                         |
| ---------------------- | ------------------------------------------------------------- |
| **1 — Chat**           | Advisor SSE, `UIPayloadRenderer`, mock tools                  |
| **2a — UI merge**      | One screen, shared session state, avatar toggle, embed layout |
| **2b — Speech bridge** | Agent `speech` drives avatar; not HeyGen vendor LLM           |
| **3 — Voice**          | Mic input on the same `thread_id`                             |

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

Avatar broker endpoints (Phase 2b) will be specified in `apps/agent/README.md` when the backend team picks them up.

## Cross-references

- [unified-advisor-avatar.md](./unified-advisor-avatar.md) — decision record and target layout
- [`apps/agent/README.md`](../apps/agent/README.md) — backend implementation handoff
- [`apps/agent/AGENTS.md`](../apps/agent/AGENTS.md) — agent instructions for backend
- [`packages/contracts/README.md`](../packages/contracts/README.md) — contract source of truth
