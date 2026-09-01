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

```
┌─────────────────────────────────────────────────────────────┐
│                    Web App (Vite + React 19)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Chat Mode   │  │  Voice Mode  │  │  Avatar View     │  │
│  │  (typed)     │  │  (speech)    │  │  (WebRTC video)  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │             │
│         └────────┬────────┴────────────────────┘             │
│                  ▼                                           │
│         ┌─────────────────┐    ┌─────────────────┐            │
│         │  Router/State   │    │  Theme (CSS)    │            │
│         └────────┬────────┘    └─────────────────┘            │
│                  ▼                                           │
│         ┌─────────────────┐                                   │
│         │  Services       │                                   │
│         └────────┬────────┘                                   │
└──────────────────┼───────────────────────────────────────────┘
                   │ HTTPS / WebSocket / WebRTC
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    Custom Backend                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LangGraph Agent (Gemini)                            │    │
│  │  Tools: portfolio, products, news, transactions      │    │
│  └─────────────────────────────────────────────────────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Actinver API │  │ News Scraper │  │ Product DB   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────┬──────────────────────────────────────────┘
                   ▼
         ┌─────────────────┐
         │ LiveAvatar API   │
         │ (sessions, LLM,  │
         │  TTS, LiveKit)   │
         └─────────────────┘
```

### Web layers

| Layer                           | Responsibility                                     |
| ------------------------------- | -------------------------------------------------- |
| `src/features/avatar/`          | LiveAvatar session, video surface, chat panel      |
| `src/features/chat/` (planned)  | Message list, composer, action chips               |
| `src/features/voice/` (planned) | Mic capture, voice UI state                        |
| `src/services/`                 | Token exchange, agent stream, future backend calls |
| `src/styles/`                   | Design tokens + Tailwind v4 wiring                 |
| `src/router.tsx`                | TanStack Router code-based tree, lazy routes       |

### Backend agent tools (planned)

| Tool                   | Purpose                                             |
| ---------------------- | --------------------------------------------------- |
| `get_portfolio`        | User holdings, allocation, performance              |
| `search_products`      | Filter by risk tier (low / medium / high)           |
| `scrape_news`          | Market and sector news for context                  |
| `explain_movement`     | Why a holding or market moved                       |
| `initiate_transaction` | Return form schema for invest / sell / retire flows |

### Transaction flow pattern

When the agent decides a transaction is needed, it returns a structured **action** with required fields. The web app renders a form (amount, product, account, confirm) before submitting to Actinver APIs.

## Patterns

### Mode switching

Chat and voice share one session context. Switching modes does not reset conversation history. Voice mode routes user speech to STT → agent → TTS/avatar; chat mode sends text directly.

### Service layer

All backend calls go through `src/services/`. Components never call `fetch` directly. See `.agents/rules/code-style-rules.md`.

### Dev proxy for API keys

`vite.config.ts` proxies `/liveavatar-api/*` → `https://api.liveavatar.com` and injects `X-API-KEY` from `.env`. The key never reaches the bundle. In production, `VITE_LIVEAVATAR_API_BASE` points at the backend.

### Feature folders

Mirror loopops-web-app convention:

```
src/features/<feature>/
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
