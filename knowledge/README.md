# LoopOps Avatar — Knowledge Base

> Structured documentation for AI agents and developers.
> Each doc follows: **Context → Architecture → Patterns → Gotchas**

## Index

| Doc                                              | Scope       | Description                                               |
| ------------------------------------------------ | ----------- | --------------------------------------------------------- |
| [poc-scope.md](./poc-scope.md)                   | POC         | What we build now vs production BA architecture           |
| [architecture.md](./architecture.md)             | System      | Web client + LiveAvatar + backend + Gemini agent overview |
| [chat-and-voice.md](./chat-and-voice.md)         | Feature     | Chat and voice modes, streaming, sessions                 |
| [heygen-live-avatar.md](./heygen-live-avatar.md) | Integration | LiveAvatar Web SDK, session lifecycle, sandbox            |
| [design-system.md](./design-system.md)           | UI          | Tailwind tokens, semantic utilities, dark mode            |
| [writing-style.md](./writing-style.md)           | Agents      | Prose style for copy and docs                             |

## Quick reference

### Tech stack

- **Vite** + **React 19** + **TypeScript**
- **TanStack Router** — code-based route tree in `apps/web/src/router.tsx`
- **Tailwind CSS v4** — tokens in `apps/web/src/styles/tokens.css`, wiring in `apps/web/src/styles/global.css`
- **@heygen/liveavatar-web-sdk** — FULL mode talking head (WebRTC)
- **Backend** — LangChain / LangGraph + Gemini (`apps/agent/`, planned)

### Key entry points

- `index.html` — app shell, fonts
- `apps/web/src/main.tsx` — React root
- `apps/web/src/router.tsx` — route tree (lazy routes from features)
- `apps/web/src/features/avatar/` — LiveAvatar demo feature
- `apps/web/src/services/` — API services (token minting)
- `apps/web/src/config/avatar.ts` — Actinver + sandbox avatar config
- `apps/agent/` — Python BFF handoff (`README.md`, `AGENTS.md`)
- `packages/contracts/` — shared API contract (`@loopops/contracts`)

### Sibling repos

| Repo                 | Use for                                                   |
| -------------------- | --------------------------------------------------------- |
| `../loopops-web-app` | Design tokens, writing style, chat architecture reference |
| `../loopops-website` | Marketing only; ignore `.agent/rules/`                    |
