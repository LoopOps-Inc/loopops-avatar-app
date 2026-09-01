---
title: Chat and Voice Modes
scope: feature
last-updated: 2026-09-01
adapted-from: ../loopops-web-app/knowledge/chat.md
---

# Chat and Voice Modes

## Context

Users interact with the Actinver advisor on a **single screen** (`/advisor`). Chat is always available. The talking avatar is optional: users toggle it on to see and hear responses, off for text-only.

Two input modes share the same `thread_id` (voice is Phase 3):

1. **Chat** — type questions, read text replies and cards; avatar lip-syncs when enabled
2. **Voice** — speak naturally; STT feeds the same agent thread; avatar responds with speech and video

Both modes use the Actinver LangGraph agent. The avatar is an output channel, not a separate conversation. See [unified-advisor-avatar.md](./unified-advisor-avatar.md).

## Architecture

### Component tree (target)

```
App
└── AdvisorSessionProvider          ← thread_id, messages, SSE handlers
    └── AdvisorPage
        ├── AvatarPanel             ← optional; WebRTC video + session controls
        ├── MessageList             ← always visible
        │   ├── MessageBubble
        │   └── UIPayloadRenderer   ← portfolio cards, attribution, sources
        ├── Composer
        ├── AvatarToggle            ← on / off
        └── VoiceControls           ← Phase 3; mic when voice mode selected
```

### File locations (target)

```
apps/web/src/features/advisor/
├── components/
│   ├── AdvisorPage.tsx
│   ├── AvatarPanel.tsx
│   ├── MessageList.tsx
│   ├── Composer.tsx
│   └── UIPayloadRenderer.tsx
├── hooks/
│   ├── use-advisor-chat.ts
│   └── use-avatar-session.ts     ← adapted from features/avatar/
└── types.ts

apps/web/src/features/avatar/       ← /demo sandbox only until Phase 2a merge
```

### Data flow

```
User input (text, or speech in Phase 3)
  → advisor-service (POST /v1/threads/{id}/messages)
  → backend agent (Gemini + tools)
  → SSE stream
       ├─ token / ui → MessageList + UIPayloadRenderer
       └─ speech (on done) → avatar-broker → LiveAvatar LITE → lip-sync

Avatar toggle OFF: skip avatar-broker; chat and cards still work.
```

### Embed layout (webview)

When `?embed=1` is set:

- Full viewport (`100dvh`), no app nav
- Avatar video fills the top when enabled
- Chat docked at the bottom with safe-area padding
- Same `AdvisorSessionProvider` state as standalone

## Patterns

### Multi-session history

Per authenticated user. Sessions stored locally (localStorage) until backend persistence is added. Auto-title from first user message.

### Streaming replies

Show thinking indicator while agent runs tools. Stream `token` events into the message list. On `done`, send the `speech` field to the avatar speak API (when avatar is on). Render `ui` events as cards via `UIPayloadRenderer`.

### Avatar toggle

| State       | Behavior                                                                         |
| ----------- | -------------------------------------------------------------------------------- |
| Off         | Text + cards only; no LiveAvatar session                                         |
| On          | Start LiveAvatar session, attach video; speak `speech` after each assistant turn |
| End session | Stop WebRTC; chat thread persists                                                |

Phase 2a may use the sandbox for video validation before the avatar-broker exists. User messages still go to the advisor API only.

### Action chips

Agent can return structured actions:

| Action type     | App behavior                                 |
| --------------- | -------------------------------------------- |
| `send_prompt`   | Send a follow-up message                     |
| `fill_composer` | Pre-fill composer text                       |
| `open_form`     | Show transaction form (invest, sell, retire) |
| `show_product`  | Navigate to product detail                   |

### Transaction forms

When `open_form` is returned, render fields from the agent schema (product, amount, account, risk acknowledgment). Validate on client, submit via backend to Actinver APIs.

### Mode persistence

Remember avatar on/off and last input mode (chat vs voice) per session. Default: avatar off, chat input on first launch.

## Gotchas

- **Never send user messages to HeyGen FULL mode** on the product path. `/demo` is for SDK testing only.
- Voice mode must handle browser mic permissions (`getUserMedia` behind a user gesture). If installed-PWA mode is targeted, validate mic on iOS standalone PWAs first; Safari tabs work.
- Do not block the UI while avatar video loads; show skeleton or last frame.
- Stream tokens to the message list; send the final `speech` string to TTS. Do not stream raw tokens to the avatar.
- Investment disclaimers appear below the composer in chat mode and as overlay when avatar is full-screen.
- User-facing copy uses i18n keys under `advisor.*`.
