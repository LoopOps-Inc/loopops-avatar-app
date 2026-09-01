---
title: System Architecture
scope: system
last-updated: 2026-09-01
---

# System Architecture

## Context

The LoopOps Avatar App is a React Native mobile client for **Actinver** customers. Users interact with a talking-head avatar powered by **HeyGen Live Avatar**, backed by a custom LLM agent (Gemini + LangChain/LangGraph) that answers investment questions, explains portfolio behavior, recommends products by risk tier, and guides transaction flows (invest, retire, sell, rebalance).

Inspired by conversational banking demos (e.g. Citi Sky), but scoped to Actinver portfolio and product data.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    React Native App                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Chat Mode   │  │  Voice Mode  │  │  Avatar View     │  │
│  │  (typed)     │  │  (speech)    │  │  (HeyGen video)  │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │             │
│         └────────┬────────┴────────────────────┘             │
│                  ▼                                           │
│         ┌─────────────────┐    ┌─────────────────┐            │
│         │  Session Store  │    │  Theme / i18n   │            │
│         └────────┬────────┘    └─────────────────┘            │
│                  ▼                                           │
│         ┌─────────────────┐                                   │
│         │  API Services   │                                   │
│         └────────┬────────┘                                   │
└──────────────────┼───────────────────────────────────────────┘
                   │ HTTPS / WebSocket / SSE
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
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │ HeyGen Live      │
         │ Avatar API       │
         └─────────────────┘
```

### Mobile layers

| Layer | Responsibility |
| ----- | -------------- |
| `src/features/avatar/` | HeyGen session, video surface, lip-sync |
| `src/features/chat/` | Message list, composer, action chips |
| `src/features/voice/` | Mic capture, STT trigger, voice UI state |
| `src/services/` | HTTP client, agent stream, avatar token exchange |
| `src/theme/` | Design tokens, light/dark semantic theme |

### Backend agent tools (planned)

| Tool | Purpose |
| ---- | ------- |
| `get_portfolio` | User holdings, allocation, performance |
| `search_products` | Filter by risk tier (low / medium / high) |
| `scrape_news` | Market and sector news for context |
| `explain_movement` | Why a holding or market moved |
| `initiate_transaction` | Return form schema for invest / sell / retire flows |

### Transaction flow pattern

When the agent decides a transaction is needed, it returns a structured **action** with required fields. The mobile app renders a form (amount, product, account, confirm) before submitting to Actinver APIs.

## Patterns

### Mode switching

Chat and voice share one session context. Switching modes does not reset conversation history. Voice mode routes user speech to STT → agent → TTS/avatar; chat mode sends text directly.

### Service layer

All backend calls go through `src/services/`. Components never call `fetch` directly. See `.agents/rules/code-style-rules.md`.

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

- HeyGen session tokens are short-lived; refresh via backend, never embed API keys in the app.
- Avatar video and agent streaming are separate channels; coordinate so lip-sync matches spoken response.
- Investment disclaimers and regulatory copy must appear in the UI (not only in agent responses).
- Primary CTA buttons use `filledDark`, not brand blue. See `knowledge/design-system.md`.
