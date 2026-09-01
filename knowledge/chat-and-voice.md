---
title: Chat and Voice Modes
scope: feature
last-updated: 2026-09-01
adapted-from: ../loopops-web-app/knowledge/chat.md
---

# Chat and Voice Modes

## Context

Users interact with the Actinver avatar in two modes:

1. **Chat mode** — type questions, read text replies, avatar lip-syncs responses
2. **Voice mode** — speak naturally, avatar responds with speech and video

Both modes use the same Gemini agent backend and share session history. Adapted from the LoopOps web app chat assistant (`../loopops-web-app/knowledge/chat.md`).

## Architecture

### Component tree (planned)

```
App
└── SessionProvider
    └── MainScreen
        ├── AvatarView              ← LiveAvatar WebRTC video surface
        ├── ModeToggle              ← chat | voice
        ├── ChatPanel               ← visible in chat mode
        │   ├── MessageList
        │   ├── Composer
        │   └── ActionChips         ← invest / sell / product links
        └── VoiceControls           ← visible in voice mode
            ├── MicButton
            └── VoiceStatusIndicator
```

### File locations (planned)

```
apps/web/src/features/chat/
├── components/ChatPanel.tsx
├── components/MessageList.tsx
├── components/Composer.tsx
├── components/ActionChips.tsx
├── hooks/use-chat-session.ts
├── services/chat-service.ts
└── types/chat.ts

apps/web/src/features/voice/
├── components/VoiceControls.tsx
├── hooks/use-voice-session.ts
└── services/voice-service.ts
```

### Data flow

```
User input (text or speech)
  → chat-service / voice-service
  → backend agent (Gemini + tools)
  → SSE or WebSocket stream
  → message store + avatar speak command
  → HeyGen lip-sync + on-screen text (chat mode)
```

## Patterns

### Multi-session history

Per authenticated user. Sessions stored locally (localStorage) until backend persistence is added. Auto-title from first user message.

### Streaming replies

Show thinking indicator while agent runs tools. Stream tokens into message list. Forward final spoken text to HeyGen for avatar output.

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

Remember last mode per session. Default to chat on first launch.

## Gotchas

- Voice mode must handle browser mic permissions (`getUserMedia` behind a user gesture). If installed-PWA mode is targeted, validate mic on iOS standalone PWAs first; Safari tabs work.
- Do not block the UI while avatar video loads; show skeleton or last frame.
- Streaming text and avatar speech can desync; prefer sending complete sentences to the avatar for natural lip-sync.
- Investment disclaimers appear below composer in chat mode and as overlay in voice mode.
- Empty state copy uses i18n keys under `chat.*` namespace.
