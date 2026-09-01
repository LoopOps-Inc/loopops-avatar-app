# Agent instructions — LoopOps Avatar App

Shared rules for **Cursor**, **GitHub Copilot**, **Claude Code**, **Gemini**, and other coding agents.

## Primary docs

| Audience                   | File                                                        |
| -------------------------- | ----------------------------------------------------------- |
| All agents                 | This file + `knowledge/`                                    |
| Cursor                     | `.cursor/rules/*.mdc`                                       |
| Gemini CLI / Gemini Assist | `GEMINI.md`                                                 |
| HeyGen Skills              | `~/.cursor/skills/heygen-skills` (avatar, video, translate) |

## HeyGen Skills

Installed at `~/.cursor/skills/heygen-skills` per [HeyGen install guide](https://github.com/heygen-com/skills/blob/master/INSTALL_FOR_AGENTS.md). Requires `HEYGEN_API_KEY` in `.env` or HeyGen MCP connected in Cursor. CLI: `~/.local/bin/heygen`.

| Design tokens (agents) | `DESIGN.md` |
| Design tokens (code) | `src/styles/tokens.css` + `src/styles/global.css` |

## Project scope

Web app for the **Actinver** talking-head avatar:

- **HeyGen LiveAvatar** for video/voice output ([docs.liveavatar.com](https://docs.liveavatar.com/)), via `@heygen/liveavatar-web-sdk` (FULL mode)
- **Custom backend** (Python or TypeScript) with LangChain / LangGraph + **Gemini**
- **Two interaction modes**: chat (typed) and conversation (voice)
- Investment portfolio Q&A, product recommendations, and guided invest/retire/sell flows
- PWA-ready; desktop and mobile browsers

Sibling repos for reference:

- `../loopops-web-app` — canonical design tokens, writing style, chat patterns; this app mirrors its stack (Vite + TanStack Router + Tailwind + TypeScript)

## Commands

```sh
npm run dev       # dev server (port 8080, /liveavatar-api proxy)
npm run build     # tsc --noEmit && vite build
npm run check     # typecheck only
npm run lint      # eslint src/
npm test          # vitest run
```

Package manager: **npm**.

## Knowledge base — always consult `knowledge/`

**Before working on any feature, read the relevant doc in [`knowledge/`](./knowledge/).** The index lives at [`knowledge/README.md`](./knowledge/README.md). Every doc follows **Context → Architecture → Patterns → Gotchas**.

When a rule should be encoded for agents, document it in `knowledge/`, not in ad-hoc instruction files.

## Mandatory rules

### Design tokens — no hardcoded colors

Use `src/styles/tokens.css` primitives and the semantic Tailwind utilities from `src/styles/global.css` (`bg-surface`, `text-content`, `bg-filled-dark`, etc.). Never scatter hex values in components.

Primary CTA buttons use **filled-dark** (`bg-filled-dark` / `text-filled-dark-fg`), not brand blue. Blue (`text-accent`, `bg-accent`) is for links and brand accents only.

### API calls — service layer only

Never use raw `fetch` in components. Place network calls in `src/services/`. The LiveAvatar API key is injected by the Vite dev proxy (`LIVEAVATAR_API_KEY` in `.env`); production tokens come from the backend.

### i18n — every user-facing string

i18n is wired: all copy goes through `t('namespace.key')` from `src/i18n`. Add keys to **both** `es.json` and `en.json`. Keep copy short and direct, following [`knowledge/writing-style.md`](./knowledge/writing-style.md): no AI filler, no em dashes, no emojis.

### Clean UI rendering

When editing JSX/TSX, ensure no stray text or typos appear outside React tags.

### Feature module layout

```
src/features/<feature>/
├── components/
├── hooks/
├── services/
└── types/
```

Shared theme: `src/styles/`. Shared services: `src/services/`. Routes: code-based tree in `src/router.tsx`, components lazy-loaded from features.
