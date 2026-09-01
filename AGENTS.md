# Agent instructions — LoopOps Avatar App

Shared rules for **Cursor**, **GitHub Copilot**, **Claude Code**, **Gemini**, and other coding agents.

## Primary docs

| Audience                   | File                                                        |
| -------------------------- | ----------------------------------------------------------- |
| All agents                 | This file + `knowledge/`                                    |
| Backend agent              | `apps/agent/AGENTS.md` + `apps/agent/README.md`             |
| Cursor                     | `.cursor/rules/*.mdc`                                       |
| Gemini CLI / Gemini Assist | `GEMINI.md`                                                 |
| HeyGen Skills              | `~/.cursor/skills/heygen-skills` (avatar, video, translate) |

## HeyGen Skills

Installed at `~/.cursor/skills/heygen-skills` per [HeyGen install guide](https://github.com/heygen-com/skills/blob/master/INSTALL_FOR_AGENTS.md). Requires `HEYGEN_API_KEY` in `.env` or HeyGen MCP connected in Cursor. CLI: `~/.local/bin/heygen`.

| Design tokens (agents) | `DESIGN.md` |
| Design tokens (code) | `apps/web/src/styles/tokens.css` + `apps/web/src/styles/global.css` |

## Project scope

Monorepo for the **Actinver** talking-head avatar:

```
apps/web/        # Vite + React frontend (this app)
services/agent/  # agent backend (Python 3.12 / FastAPI / LangGraph / Gemini); docs in services/agent/docs
apps/web/           # Vite + React frontend
apps/agent/         # Python BFF — not implemented; see apps/agent/README.md
packages/contracts/ # Shared API contract (TypeScript + Zod)
```

- **HeyGen LiveAvatar** for video output ([docs.liveavatar.com](https://docs.liveavatar.com/)), via `@heygen/liveavatar-web-sdk`. FULL mode at `/demo` (sandbox dev only); LITE mode on `/advisor` (product, Phase 2b).
- **Custom backend** (Python or TypeScript) with LangChain / LangGraph + **Gemini** — see reference architecture in the sibling repo `actinver-ai-advisor`
- **Unified advisor screen** (`/advisor`): one chat thread with optional talking avatar toggle. Embeds use `?embed=1`. See [`knowledge/unified-advisor-avatar.md`](./knowledge/unified-advisor-avatar.md).
- **Input modes** (Phase 3 for voice): typed chat and conversation (voice) share the same `thread_id`
- Investment portfolio Q&A, product recommendations, and guided invest/retire/sell flows
- PWA-ready; desktop and mobile browsers

All frontend source lives under `apps/web/` — feature layout, tokens, and services are relative to that directory.

Sibling repos for reference:

- `../loopops-web-app` — canonical design tokens, writing style, chat patterns; this app mirrors its stack (Vite + TanStack Router + Tailwind + TypeScript)
- `../actinver-ai-advisor` — reference architecture for the monorepo layout (`apps/`, `packages/`, `infra/`, `docs/`)

## Commands

```sh
npm run dev       # dev server (port 8080, /liveavatar-api proxy)
npm run build     # tsc --noEmit && vite build
npm run check     # typecheck only
npm run lint      # eslint apps/web/src/
npm test          # vitest run
```

Root scripts delegate to the `apps/web` workspace (`npm -w apps/web`). Run them from the repo root.

Package manager: **npm**.

## Knowledge base — always consult `knowledge/`

**Before working on any feature, read the relevant doc in [`knowledge/`](./knowledge/).** The index lives at [`knowledge/README.md`](./knowledge/README.md). Every doc follows **Context → Architecture → Patterns → Gotchas**.

When a rule should be encoded for agents, document it in `knowledge/`, not in ad-hoc instruction files.

## Mandatory rules

### Design tokens — no hardcoded colors

Use `apps/web/src/styles/tokens.css` primitives and the semantic Tailwind utilities from `apps/web/src/styles/global.css` (`bg-surface`, `text-content`, `bg-filled-dark`, etc.). Never scatter hex values in components.

Primary CTA buttons use **filled-dark** (`bg-filled-dark` / `text-filled-dark-fg`), not brand blue. Blue (`text-accent`, `bg-accent`) is for links and brand accents only.

### API calls — service layer only

Never use raw `fetch` in components. Place network calls in `apps/web/src/services/`. The LiveAvatar API key is injected by the Vite dev proxy (`LIVEAVATAR_API_KEY` in `apps/web/.env`); production tokens come from the backend.

### i18n — every user-facing string

i18n is wired: all copy goes through `t('namespace.key')` from `apps/web/src/i18n`. Add keys to **both** `es.json` and `en.json`. Keep copy short and direct, following [`knowledge/writing-style.md`](./knowledge/writing-style.md): no AI filler, no em dashes, no emojis.

### Clean UI rendering

When editing JSX/TSX, ensure no stray text or typos appear outside React tags.

### Feature module layout

```
apps/web/src/features/<feature>/
├── components/
├── hooks/
├── services/
└── types/
```

Shared theme: `apps/web/src/styles/`. Shared services: `apps/web/src/services/`. Routes: code-based tree in `apps/web/src/router.tsx`, components lazy-loaded from features.
