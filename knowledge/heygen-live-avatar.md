---
title: HeyGen Live Avatar
scope: integration
last-updated: 2026-09-01
docs: https://docs.liveavatar.com/
skills: ~/.cursor/skills/heygen-skills
---

# HeyGen Live Avatar

## Context

The talking-head avatar uses **HeyGen LiveAvatar** in the web app. Docs: [docs.liveavatar.com](https://docs.liveavatar.com/).

The avatar renders video of a digital presenter that lip-syncs agent responses. In voice mode it is the primary output channel; in chat mode it supplements text replies. The platform exposes three modes; this app uses **FULL mode** (LiveAvatar manages STT → LLM → TTS inside a LiveKit room).

### HeyGen Skills (agent tooling)

Installed per [HeyGen INSTALL_FOR_AGENTS](https://github.com/heygen-com/skills/blob/master/INSTALL_FOR_AGENTS.md):

| Item              | Location                                       |
| ----------------- | ---------------------------------------------- |
| Skills repo       | `~/.cursor/skills/heygen-skills`               |
| Avatar skill      | `heygen-avatar/SKILL.md`                       |
| Video skill       | `heygen-video/SKILL.md`                        |
| CLI               | `~/.local/bin/heygen`                          |
| API key (project) | `.env` → `HEYGEN_API_KEY` (see `.env.example`) |

Auth priority: CLI + `HEYGEN_API_KEY` → MCP OAuth (if connected in Cursor) → CLI session (`heygen auth login`).

**Note:** Setting `HEYGEN_API_KEY` short-circuits MCP detection and uses direct API billing instead of plan credits.

### Actinver avatar (configured)

| Field                      | Value                                                              |
| -------------------------- | ------------------------------------------------------------------ |
| Identity file              | `AVATAR-ACTINVER.md`                                               |
| App config                 | `apps/web/src/config/avatar.ts`                                             |
| Group ID                   | `378cae579aef4c1189398b008dec0cd1`                                 |
| Look ID (landscape)        | `f00b90bab23243bc93a1484ebd63d8c9`                                 |
| Look ID (portrait, mobile) | `ec08a8bb0119489aa0019a090274c631`                                 |
| Voice                      | Jorge - Professional (`d62a0ce960434056b25c058bc4fa2509`, Spanish) |

Live Avatar session tokens use `LIVEAVATAR_API_KEY` from [app.liveavatar.com](https://app.liveavatar.com), not the standard HeyGen API key.

## Architecture

### Integration layers

| Layer                                                 | Responsibility                                                   |
| ----------------------------------------------------- | ---------------------------------------------------------------- |
| Backend (production)                                  | Create LiveAvatar sessions, hold API keys, return session tokens |
| `apps/web/src/services/liveavatar-service.ts`                  | Mint session tokens (dev proxy), future backend calls            |
| `apps/web/src/features/avatar/`                                | SDK session lifecycle, video surface, chat panel                 |
| `apps/web/src/features/avatar/hooks/use-liveavatar-session.ts` | React glue over the SDK (events → state)                         |

### Session lifecycle

```
1. User opens /demo and starts a session
2. liveavatar-service POSTs /v1/sessions/token (mode FULL, is_sandbox true in dev)
   - dev: Vite proxy /liveavatar-api → https://api.liveavatar.com, injects X-API-KEY
   - prod: backend mints the token
3. new LiveAvatarSession(token, { voiceChat }) + session.start()
4. SESSION_STREAM_READY → session.attach(<video>) renders the avatar
5. Typed messages: session.message(text) → avatar replies with voice + transcriptions
6. TRANSCRIPTION events build the chat history
7. session.stop() on end / unmount → DISCONNECTED cleanup
```

### Sandbox mode

[docs.liveavatar.com/docs/sandbox-mode](https://docs.liveavatar.com/docs/sandbox-mode)

- `is_sandbox: true` in the token request
- Only the Wayne avatar (`dd73ea75-1218-4ef3-92ce-606d5f7fbc0a`) is available
- Sessions auto-terminate after ~1 minute
- No credit usage
- Defaults in `apps/web/src/config/avatar.ts` → `liveAvatarSandbox`

## Patterns

### Token security

- API keys live server-side only. In dev the Vite proxy (`vite.config.ts`) injects `X-API-KEY` from `.env`; the key never reaches the bundle.
- The client receives short-lived session tokens.
- In production, `VITE_LIVEAVATAR_API_BASE` points at the backend that mints tokens.

### React glue over the SDK

`use-liveavatar-session.ts` adapts the official demo wrapper:

- The session instance is created once per mount via a lazy `useState` initializer. Never create it inside an effect: React StrictMode double-invokes effects and would spawn two LiveKit rooms (one orphaned session still running server-side).
- `start()` is idempotent (guard ref) so StrictMode's double effect run cannot double-start.
- Consumers remount with a fresh token per session; session tokens are one-shot.
- User transcription chunks are cumulative (full phrase so far) — replace the last user message.
- Avatar chunks are individual words — append.
- On `DISCONNECTED`, remove all listeners and reset stream state.
- Distinguish user-initiated stop from server stop (`onEnded(reason)`): sandbox sessions are killed by the server after ~1 minute.

### Chat + voice

FULL mode answers typed messages with voice and transcripts. Voice input (`voiceChat: true`) requires mic permission (`getUserMedia`); enable only behind a user gesture.

## Gotchas

- **Sandbox voices**: `voice_id` must exist in the LiveAvatar space. HeyGen catalog voice IDs (e.g. Actinver's Jorge) are rejected at `/v1/sessions/start` with `Voice not found` (validation is lazy: token minting succeeds, start fails 400). In sandbox, omit `voice_id` to use Wayne's default voice.
- Test on real devices/browsers; simulators and headless environments may lack WebRTC codecs.
- Video autoplay requires a user gesture (the demo starts the session from a button click).
- The SDK is v0.x — API may change; check the [demo app](https://github.com/heygen-com/liveavatar-web-sdk/tree/master/apps/demo) when upgrading.
- `avatar_persona` is deprecated upstream in favor of `voice_agent`; sandbox docs still use it. Plan the swap before production.
- Coordinate avatar `speaking` state with voice mode mic (disable mic while avatar talks to avoid echo).
- Session cost: destroy idle sessions after timeout; use `keepAlive()` only while the user is active.
- Follow LiveAvatar rate limits; queue messages if responses arrive faster than playback.
