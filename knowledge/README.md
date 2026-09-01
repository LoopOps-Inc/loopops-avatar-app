# LoopOps Avatar — Knowledge Base

> Structured documentation for AI agents and developers.
> Each doc follows: **Context → Architecture → Patterns → Gotchas**

## Index

| Doc                                              | Scope       | Description                                               |
| ------------------------------------------------ | ----------- | --------------------------------------------------------- |
| [architecture.md](./architecture.md)             | System      | Web client + LiveAvatar + backend + Gemini agent overview |
| [chat-and-voice.md](./chat-and-voice.md)         | Feature     | Chat and voice modes, streaming, sessions                 |
| [heygen-live-avatar.md](./heygen-live-avatar.md) | Integration | LiveAvatar Web SDK, session lifecycle, sandbox            |
| [design-system.md](./design-system.md)           | UI          | Tailwind tokens, semantic utilities, dark mode            |
| [writing-style.md](./writing-style.md)           | Agents      | Prose style for copy and docs                             |

## Quick reference

### Tech stack

- **Vite** + **React 19** + **TypeScript**
- **TanStack Router** — code-based route tree in `src/router.tsx`
- **Tailwind CSS v4** — tokens in `src/styles/tokens.css`, wiring in `src/styles/global.css`
- **@heygen/liveavatar-web-sdk** — FULL mode talking head (WebRTC)
- **Backend** — LangChain / LangGraph + Gemini, investment tools (planned)

### Key entry points

- `index.html` — app shell, fonts
- `src/main.tsx` — React root
- `src/router.tsx` — route tree (lazy routes from features)
- `src/features/avatar/` — LiveAvatar demo feature
- `src/services/` — API services (token minting)
- `src/config/avatar.ts` — Actinver + sandbox avatar config

### Sibling repos

| Repo                 | Use for                                                   |
| -------------------- | --------------------------------------------------------- |
| `../loopops-web-app` | Design tokens, writing style, chat architecture reference |
| `../loopops-website` | Marketing only; ignore `.agent/rules/`                    |
