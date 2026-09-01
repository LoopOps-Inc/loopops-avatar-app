# LoopOps Avatar — Knowledge Base

> Structured documentation for AI agents and developers.
> Each doc follows: **Context → Architecture → Patterns → Gotchas**

## Index

| Doc | Scope | Description |
| --- | ----- | ----------- |
| [architecture.md](./architecture.md) | System | Mobile + HeyGen + backend + Gemini agent overview |
| [chat-and-voice.md](./chat-and-voice.md) | Feature | Chat and voice modes, streaming, sessions |
| [heygen-live-avatar.md](./heygen-live-avatar.md) | Integration | Live Avatar SDK, session lifecycle |
| [design-system.md](./design-system.md) | UI | RN theme tokens, semantic colors, dark mode |
| [writing-style.md](./writing-style.md) | Agents | Prose style for copy and docs |

## Quick reference

### Tech stack

- **React Native 0.87** + **React 19** + **TypeScript**
- **HeyGen Live Avatar** — video talking head
- **Backend** — LangChain / LangGraph + Gemini, investment tools
- **Theme** — `src/theme/tokens.ts` (ported from loopops-web-app `DESIGN.md`)

### Key entry points

- `App.tsx` — root component
- `src/theme/tokens.ts` — design tokens and `getTheme()`
- `src/services/` — API client (to be added)
- `src/features/` — feature modules (avatar, chat, voice)

### Sibling repos

| Repo | Use for |
| ---- | ------- |
| `../loopops-web-app` | Design tokens, writing style, chat architecture reference |
| `../loopops-website` | Marketing only; ignore `.agent/rules/` |
