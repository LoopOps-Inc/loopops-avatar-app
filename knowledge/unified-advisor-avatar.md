---
title: Unified Advisor + Avatar
scope: decision
status: accepted
date: 2026-09-01
last-updated: 2026-09-01
---

# Unified Advisor + Avatar

## Context

The web app shipped two separate routes:

| Route      | What it did                                                  |
| ---------- | ------------------------------------------------------------ |
| `/advisor` | Actinver AI chat (LangGraph agent, SSE, rich cards)          |
| `/demo`    | HeyGen LiveAvatar sandbox (FULL mode, HeyGen's built-in LLM) |

These were split during early POC work: chat advisor first, avatar integration second. In practice they are **not the same conversation**. A message in Advisor goes to the Actinver agent; the same message in Demo goes to HeyGen's Wayne avatar and its own LLM.

The product goal is different. Users (and the host app via webview) need **one advisor session** where they can turn the talking avatar on or off without losing chat history. The avatar is an output channel, not a second app.

## Decision

**Merge Advisor and Demo into a single `/advisor` experience.**

- One `thread_id`, one message list, one composer.
- Avatar is optional and toggleable within the same screen.
- `/demo` remains as an **internal HeyGen sandbox** for SDK and session lifecycle testing. It is not the user-facing product route.
- Embeds load `/advisor?embed=1` (full viewport, no nav).

## Rationale

1. **One brain** — Portfolio answers, market data, and cards must come from the Actinver LangGraph agent, not HeyGen's vendor LLM.
2. **One thread** — Switching avatar on/off must not reset history. Host apps embed a single URL.
3. **Split-channel rendering** — The agent already returns `speech` (qualitative narrative) and `ui_payload[]` (exact figures). Text and cards render in chat; `speech` drives avatar lip-sync. Exact numbers never go to the avatar vendor.
4. **Mobile-first embed** — The host app opens a webview. Layout is full-screen video on top, chat docked at the bottom (implemented in the avatar session panel, now the target layout for `/advisor`).

## Architecture

### Target screen layout

```
┌─────────────────────────────────────┐
│  AvatarView (optional, collapsible) │  ← WebRTC video when avatar is ON
│  [CONNECTED] [GOOD]          [End]  │
├─────────────────────────────────────┤
│  MessageList                        │  ← advisor thread (text + UIPayloadRenderer)
│  · user bubble                      │
│  · assistant bubble + cards           │
├─────────────────────────────────────┤
│  [input....................] [Send] │
│  [Avatar on/off]  [Voice · later]   │
└─────────────────────────────────────┘
```

### Data flow (target)

```
User text (composer)
  → POST /v1/threads/{thread_id}/messages
  → LangGraph agent (Gemini + tools)
  → SSE stream
       ├─ token / ui events → MessageList + UIPayloadRenderer
       └─ speech (on done)   → avatar-broker → LiveAvatar LITE → lip-sync video

Avatar toggle OFF: skip the avatar-broker path; chat still works.
Avatar toggle ON:  subscribe to WebRTC video; speak agent `speech` only.
```

### What `/demo` is for (sandbox only)

`/demo` keeps **HeyGen FULL mode** (vendor STT → vendor LLM → vendor TTS). Use it to validate:

- Session token minting and dev proxy
- WebRTC attach, connection quality, interrupt, keep-alive
- Mobile full-viewport layout

Do **not** point end users or embeds at `/demo`. It does not use the Actinver agent.

### Route map (after merge)

| Route              | Audience               | Purpose                                |
| ------------------ | ---------------------- | -------------------------------------- |
| `/advisor`         | Product, webview embed | Unified advisor chat + optional avatar |
| `/advisor?embed=1` | Host app webview       | Same, no nav, full viewport            |
| `/demo`            | Developers             | HeyGen sandbox spike only              |

## POC phasing

Replaces the old "Phase 1 chat, Phase 2 avatar on separate demo" plan.

| Phase                             | Deliverable                                                                | Avatar behavior                                                |
| --------------------------------- | -------------------------------------------------------------------------- | -------------------------------------------------------------- |
| **1 — Chat** (done / in progress) | `/advisor` with mock or real SSE, `UIPayloadRenderer`                      | Avatar off; text-only                                          |
| **2a — UI merge**                 | Single screen: mobile layout, shared `useAdvisorChat` state, avatar toggle | Toggle shows video panel; session lifecycle from sandbox hooks |
| **2b — Speech bridge**            | Forward agent `speech` to avatar speak API when backend exposes it         | Avatar lip-syncs Actinver answers, not HeyGen LLM              |
| **3 — Voice**                     | Mic capture, STT → same thread                                             | Voice and typed input share history                            |

Phase 2a can ship before the BFF avatar-broker exists. The toggle may start/stop a sandbox video session for layout and SDK validation while chat stays on the advisor thread. Phase 2b wires the real speech path.

### In scope for POC (updated)

| Area     | Deliverable                                                            |
| -------- | ---------------------------------------------------------------------- |
| Contract | `speech` + `ui_payload[]` per turn (`@loopops/contracts`)              |
| Backend  | Sessions, chat SSE, mock tools; later avatar-broker endpoint           |
| Frontend | Unified `/advisor` screen, embed mode, avatar toggle                   |
| HeyGen   | Sandbox validation at `/demo`; LITE integration via broker in Phase 2b |

### Out of scope (unchanged)

- Microservice split, WORM audit, DPoP auth
- Real Actinver core APIs
- Full voice mode before Phase 3

## Patterns

### Shared session state

Lift `useAdvisorChat` into a `SessionProvider` (or equivalent) at the advisor route level. Avatar hooks read the same `thread_id` and message list. Toggling avatar mounts or unmounts the WebRTC surface without clearing messages.

### Avatar toggle

- **Off (default):** Composer sends to advisor API only. No LiveAvatar session.
- **On:** Mint session token (sandbox in dev, broker in prod), attach video, on each assistant `done` event send `speech` to speak command.
- **End:** Stop LiveAvatar session; chat thread persists.

### Embed contract for host apps

```
URL:     https://<host>/advisor?embed=1
Layout:  100dvh, safe-area insets, chat pinned to bottom
Nav:     hidden
Locale:  same i18n keys as standalone (`advisor.*`)
```

### File layout (target)

```
apps/web/src/features/advisor/
├── components/
│   ├── AdvisorPage.tsx          # unified screen
│   ├── AdvisorMessageList.tsx
│   ├── AdvisorComposer.tsx
│   ├── AvatarPanel.tsx          # video surface + session controls (from avatar feature)
│   └── UIPayloadRenderer.tsx
├── hooks/
│   ├── use-advisor-chat.ts      # thread + SSE
│   └── use-avatar-session.ts    # LiveAvatar lifecycle (adapted from use-liveavatar-session)
└── types.ts

apps/web/src/features/avatar/      # keep for /demo sandbox only
```

## Gotchas

- **Do not route user messages through HeyGen FULL mode** in the product path. That bypasses Actinver tools, compliance copy, and `ui_payload` cards.
- **Speech vs tokens** — Stream `token` events into the message list for reading; send the final `speech` string to the avatar for lip-sync. Do not stream raw tokens to TTS.
- **Session cost** — LiveAvatar sessions are short-lived and metered. Start on toggle ON, stop on toggle OFF or page leave.
- **Sandbox limit** — `/demo` sandbox sessions last ~1 minute and use the Wayne avatar only. Production uses the Actinver look IDs in `apps/web/src/config/avatar.ts`.
- **StrictMode** — LiveAvatar session hooks must not double-create sessions on mount. See `use-liveavatar-session.ts` comments.

## Cross-references

- [poc-scope.md](./poc-scope.md) — updated POC boundaries
- [architecture.md](./architecture.md) — runtime diagram and split-channel rendering
- [chat-and-voice.md](./chat-and-voice.md) — mode switching and streaming patterns
- [heygen-live-avatar.md](./heygen-live-avatar.md) — FULL (sandbox) vs LITE (production)
