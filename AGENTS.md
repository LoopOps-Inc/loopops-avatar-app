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

- **Backend-owned avatar media**: the agent backend (`services/agent`) serves avatar sessions via `POST /v1/avatar/session` (LiveKit URL + token, audio WebSocket); the web app renders them with `livekit-client` on `/demo`.
- **Custom backend** (Python or TypeScript) with LangChain / LangGraph + **Gemini** — see reference architecture in the sibling repo `actinver-ai-advisor`
- **Live session** (`/demo`): talking-head session plus chat transcript. `/` redirects here. See [`knowledge/unified-advisor-avatar.md`](./knowledge/unified-advisor-avatar.md).
- **Input modes** (Phase 3 for voice): typed chat and conversation (voice) share the same `thread_id`
- Investment portfolio Q&A, product recommendations, and guided invest/retire/sell flows
- PWA-ready; desktop and mobile browsers

All frontend source lives under `apps/web/` — feature layout, tokens, and services are relative to that directory.

Sibling repos for reference:

- `../loopops-web-app` — canonical design tokens, writing style, chat patterns; this app mirrors its stack (Vite + TanStack Router + Tailwind + TypeScript)
- `../actinver-ai-advisor` — reference architecture for the monorepo layout (`apps/`, `packages/`, `infra/`, `docs/`)

## Commands

```sh
npm run dev       # dev server (port 8080, /api proxy -> http://localhost:8443; needs AGENT_DEV_TOKEN in apps/web/.env)
npm run build     # tsc --noEmit && vite build
npm run check     # typecheck only
npm run lint      # eslint apps/web/src/
npm test          # vitest run
docker compose up -d --build   # full stack: web on :8080 + agent on :8443
docker compose logs -f web
```

After changing auth env vars, recreate the agent and web-token containers so a fresh token is minted: `docker compose up -d --force-recreate agent web-token web`.

Root scripts delegate to the `apps/web` workspace (`npm -w apps/web`). Run them from the repo root.

Package manager: **npm**.

## Knowledge base — always consult `knowledge/`

**Before working on any feature, read the relevant doc in [`knowledge/`](./knowledge/).** The index lives at [`knowledge/README.md`](./knowledge/README.md). Every doc follows **Context → Architecture → Patterns → Gotchas**.

When a rule should be encoded for agents, document it in `knowledge/`, not in ad-hoc instruction files.

## Mandatory rules

### Design tokens — no hardcoded colors

Use `apps/web/src/styles/tokens.css` primitives and the semantic Tailwind utilities from `apps/web/src/styles/global.css` (`bg-surface`, `text-content`, `bg-filled-dark`, etc.). Never scatter hex values in components.

Primary CTA buttons use **filled-dark** (`bg-filled-dark` / `text-filled-dark-fg`), not brand blue. There is no accent blue token today; add `brand-accent-50` back to `tokens.css` and `global.css` when a screen needs links or brand accents.

### API calls — service layer only

Never use raw `fetch` in components. Place network calls in `apps/web/src/services/`. `npm run dev` proxies `/api` to `http://localhost:8443`; the dev bearer token (`AGENT_DEV_TOKEN` in `apps/web/.env`) is injected by the Vite proxy and never reaches the client bundle.

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
