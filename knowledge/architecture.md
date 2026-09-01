---
title: System Architecture
scope: system
last-updated: 2026-09-01
---

# System Architecture

## Context

The LoopOps Avatar App is a **web client** for **Actinver** customers. Users interact with a talking-head avatar powered by **HeyGen LiveAvatar**, backed by a custom LLM agent (Gemini + LangChain/LangGraph) that answers investment questions, explains portfolio behavior, recommends products by risk tier, and guides transaction flows (invest, retire, sell, rebalance).

Inspired by conversational banking demos (e.g. Citi Sky), but scoped to Actinver portfolio and product data. Runs on desktop and mobile browsers; PWA-ready.

## Architecture

### Monorepo layout

```
loopops-avatar-app/
├── apps/
│   ├── web/                 # Vite + React 19 (npm workspace) — LIVE
│   └── agent/               # Python FastAPI + LangGraph BFF — PLANNED
├── packages/
│   └── contracts/           # @loopops/contracts — shared API types (Zod)
└── knowledge/               # architecture docs
```

### Runtime (POC)

Solid lines = implemented today. Dashed = planned.

`/advisor` is the product route (chat + optional avatar on one thread).
`/demo` is an internal HeyGen FULL-mode sandbox. See [unified-advisor-avatar.md](./unified-advisor-avatar.md).

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Browser (desktop / mobile / webview embed)                              │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │  apps/web  (Vite + React 19 + TanStack Router)                     │  │
│  │                                                                    │  │
│  │  ┌─────────────────────────────┐  ┌───────────┐  ┌───────────────┐ │  │
│  │  │ /advisor  (product)         │  │ /demo     │  │ Theme + i18n  │ │  │
│  │  │ chat + cards + avatar toggle│  │ dev only  │  │ styles/ i18n/ │ │  │
│  │  │ ?embed=1 for webview        │  │ sandbox   │  └───────────────┘ │  │
│  │  └──────────────┬──────────────┘  └─────┬─────┘                  │  │
│  │                 │                         │                        │  │
│  │                 │  SSE (token, ui, done)  │  FULL mode (vendor LLM)│  │
│  │                 └────────────┐            │                        │  │
│  │                              │            │                        │  │
│  │  apps/web/src/services/      │            │  liveavatar-service    │  │
│  │  advisor-service.ts          │            │                        │  │
│  └──────────────────────────────┼────────────┼────────────────────────┘  │
└─────────────────────────────────┼────────────┼────────────────────────────┘
                                  │ HTTPS      │ HTTPS
                                  │ /api → :8000 │ /liveavatar-api (dev proxy)
                                  ▼            ▼
                    ┌────────────────────────────────────────┐
                    │  apps/agent  (Python BFF)  PLANNED     │
                    │  ┌──────────────────────────────────┐  │
                    │  │  LangGraph agent (Gemini)        │  │
                    │  │  route → tools → composer        │  │
                    │  └───────────────┬──────────────────┘  │
                    │                  │ mock tools (POC)     │
                    │                  ▼                      │
                    │         portfolio · market · news       │
                    │                  │                      │
                    │                  │ speech (Phase 2b)    │
                    │                  ▼                      │
                    │         avatar-broker ──► LiveAvatar    │
                    └────────────────────────────────────────┘
                                  │
              packages/contracts ◄┘
              (SessionResponse, UIComponent, SSE events)
```

### Split-channel rendering (advisor path)

When `apps/agent` ships, every agent turn produces two outputs. Exact figures never go to the avatar vendor.

```
                    AgentTurnOutput
                    ┌─────────────────────────────┐
                    │  speech   (qualitative only)  │
                    │  ui_payload[] (exact data)  │
                    └──────────┬──────────┬────────┘
                               │          │
              narrative ───────┘          └────── exact figures
              (future: TTS → avatar)            (UIPayloadRenderer in /advisor)
```

### Target-state (post-POC)

```
apps/web ──HTTPS/SSE──► apps/agent ──► LangGraph + Gemini
                            │
                            ├── tool-gateway ──► Actinver core APIs
                            ├── Vertex AI (STT / TTS)
                            └── avatar-broker ──► LiveAvatar LITE + LiveKit
                                      │
apps/web ◄──────── WebRTC subscribe ──┘  (video only; audio from our pipeline)
```

See sibling repo `actinver-ai-advisor` for the full production architecture.

### Web layers

| Layer                            | Status              | Responsibility                                                  |
| -------------------------------- | ------------------- | --------------------------------------------------------------- |
| `apps/web/src/features/advisor/` | In progress         | Unified screen: chat, cards, avatar toggle, embed layout        |
| `apps/web/src/features/avatar/`  | Live (`/demo` only) | HeyGen sandbox spike; code migrates into advisor in Phase 2a    |
| `apps/web/src/features/voice/`   | Planned (Phase 3)   | Mic capture, voice UI on same `thread_id`                       |
| `apps/web/src/services/`         | Partial             | `advisor-service.ts` + `liveavatar-service.ts`                  |
| `apps/web/src/styles/`           | Live                | Design tokens + Tailwind v4 wiring                              |
| `apps/web/src/router.tsx`        | Live                | TanStack Router tree, lazy routes                               |
| `packages/contracts/`            | Live                | Shared API types (`SessionResponse`, `UIComponent`, SSE events) |
| `apps/agent/`                    | Planned             | Python BFF — see `apps/agent/README.md`                         |

### Backend agent tools (POC v0, planned)

| Tool                        | Purpose                                          |
| --------------------------- | ------------------------------------------------ |
| `get_portfolio_performance` | Holdings valuation, period return                |
| `get_portfolio_attribution` | Why the portfolio moved (basis points by sleeve) |
| `search_market_news`        | Allow-listed news with citations                 |
| `get_market_quote`          | FX and index quotes with timestamps              |

Full catalogue: `actinver-ai-advisor/docs/04-backend/03-tool-catalog.md`.

### Transaction flow pattern

When the agent decides a transaction is needed, it returns a structured **action** with required fields. The web app renders a form (amount, product, account, confirm) before submitting to Actinver APIs.

## Patterns

### Mode switching

Chat and voice share one session context. Switching modes does not reset conversation history. Voice mode routes user speech to STT → agent → TTS/avatar; chat mode sends text directly.

### Service layer

All backend calls go through `apps/web/src/services/`. Components never call `fetch` directly. See `.agents/rules/code-style-rules.md`.

### Dev proxy for API keys

`apps/web/vite.config.ts` proxies `/liveavatar-api/*` → `https://api.liveavatar.com` and injects `X-API-KEY` from `.env`. The key never reaches the bundle.

When `apps/agent` is ready, add a second proxy: `/api` → `http://localhost:8000`. In production, `VITE_ADVISOR_API_BASE` points at the deployed BFF.

### Feature folders

Mirror loopops-web-app convention:

```
apps/web/src/features/<feature>/
├── components/
├── hooks/
├── services/
└── types/
```

## Gotchas

- LiveAvatar session tokens are short-lived; refresh via backend, never embed API keys in the client.
- Avatar video and agent streaming are separate channels; coordinate so lip-sync matches spoken response.
- Investment disclaimers and regulatory copy must appear in the UI (not only in agent responses).
- Primary CTA buttons use `bg-filled-dark`, not brand blue. See `knowledge/design-system.md`.
- If a PWA (installed standalone mode) is targeted, validate `getUserMedia` on iOS installed PWAs before committing to voice mode there; Safari tabs work.
