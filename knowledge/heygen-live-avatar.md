---
title: HeyGen Live Avatar
scope: integration
last-updated: 2026-09-01
docs: https://docs.liveavatar.com/
skills: ~/.cursor/skills/heygen-skills
---

# HeyGen Live Avatar

## Context

The talking-head avatar uses **HeyGen Live Avatar** embedded in the React Native app. Docs: [docs.liveavatar.com](https://docs.liveavatar.com/).

The avatar renders video of a digital presenter that lip-syncs agent responses. In voice mode it is the primary output channel; in chat mode it supplements text replies.

### HeyGen Skills (agent tooling)

Installed per [HeyGen INSTALL_FOR_AGENTS](https://github.com/heygen-com/skills/blob/master/INSTALL_FOR_AGENTS.md):

| Item | Location |
| ---- | -------- |
| Skills repo | `~/.cursor/skills/heygen-skills` |
| Avatar skill | `heygen-avatar/SKILL.md` |
| Video skill | `heygen-video/SKILL.md` |
| CLI | `~/.local/bin/heygen` |
| API key (project) | `.env` → `HEYGEN_API_KEY` (see `.env.example`) |

Auth priority: CLI + `HEYGEN_API_KEY` → MCP OAuth (if connected in Cursor) → CLI session (`heygen auth login`).

**Note:** Setting `HEYGEN_API_KEY` short-circuits MCP detection and uses direct API billing instead of plan credits.

### Actinver avatar (configured)

| Field | Value |
| ----- | ----- |
| Identity file | `AVATAR-ACTINVER.md` |
| App config | `src/config/avatar.ts` |
| Group ID | `378cae579aef4c1189398b008dec0cd1` |
| Look ID (landscape) | `f00b90bab23243bc93a1484ebd63d8c9` |
| Look ID (portrait, mobile) | `ec08a8bb0119489aa0019a090274c631` |
| Voice | Jorge - Professional (`d62a0ce960434056b25c058bc4fa2509`, Spanish) |

Live Avatar session tokens use `HEYGEN_LIVE_AVATAR_API_KEY` from [app.liveavatar.com](https://app.liveavatar.com), not the standard HeyGen API key.

## Architecture

### Integration layers

| Layer                            | Responsibility                                                         |
|----------------------------------|------------------------------------------------------------------------|
| Backend                          | Create HeyGen sessions, hold API keys, return session tokens to mobile |
| `src/features/avatar/`           | Initialize SDK, render video, manage session lifecycle                 |
| `src/services/avatar-service.ts` | Request tokens from backend, refresh on expiry                         |

### Session lifecycle

```
1. User opens app / starts conversation
2. Mobile requests avatar session token from backend
3. Backend calls HeyGen API → returns token + session config
4. Mobile initializes Live Avatar with token
5. Agent response text → backend or mobile forwards to avatar speak API
6. Avatar renders lip-synced video
7. On background / logout → destroy session, release resources
```

### React Native considerations

- Live Avatar may require a **WebView** or native SDK wrapper depending on HeyGen RN support at integration time.
- Video surface needs dedicated layout region (top half or full screen in voice mode).
- Handle network drops: reconnect session or show graceful fallback to text-only chat.

## Patterns

### Token security

- API keys live on backend only.
- Mobile receives short-lived session tokens.
- Refresh tokens before expiry without interrupting conversation.

### Speak command

After agent completes a response:

1. Finalize text (complete sentences preferred for lip-sync).
2. Send to HeyGen speak/stream endpoint.
3. Update UI state: `speaking` → `idle`.

### Layout modes

| Mode  | Avatar layout                                 |
|-------|-----------------------------------------------|
| Chat  | Avatar thumbnail or top panel; messages below |
| Voice | Avatar full width; minimal chrome; mic FAB    |

## Gotchas

- Test on real devices; simulators may not support WebRTC or camera/mic paths.
- Coordinate avatar `speaking` state with voice mode mic (disable mic while avatar talks to avoid echo).
- Session cost: destroy idle sessions after timeout.
- Follow HeyGen rate limits; queue speak commands if responses arrive faster than playback.
