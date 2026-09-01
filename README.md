# LoopOps Avatar App — Monorepo

Monorepo for the Actinver talking-head avatar: web frontend (HeyGen LiveAvatar + custom LLM backend). Runs on desktop and mobile browsers, PWA-ready.

```
├── apps/
│   └── web/          # Vite + React 19 frontend
├── services/
│   └── agent/        # agent backend placeholder (Python / FastAPI / LangGraph, reserved)
├── knowledge/        # architecture docs (read before coding)
└── package.json      # npm workspaces root
```

Reference architecture: sibling repo `actinver-ai-advisor`.

## Stack (apps/web)

- Vite + React 19 + TypeScript
- TanStack Router
- Tailwind CSS v4 + LoopOps design tokens (`apps/web/src/styles/`)
- `@heygen/liveavatar-web-sdk` (FULL mode, WebRTC)
- `lucide-react` icons
- Vitest + Testing Library

Mirrors `../loopops-web-app` conventions. i18n via `apps/web/src/i18n` (es/en, `t('demo.key')`), dark mode follows `prefers-color-scheme`, PWA manifest + favicon in `apps/web/public/`.

## Setup

```sh
npm install
cp apps/web/.env.example apps/web/.env
```

Set `LIVEAVATAR_API_KEY` in `apps/web/.env` (from https://app.liveavatar.com, Developers page). The Vite dev proxy injects it as `X-API-KEY`, so the key never reaches the client bundle.

## Run

Root scripts delegate to the `apps/web` workspace; run them from the repo root.

```sh
npm run dev       # http://localhost:8080
npm run build     # typecheck + production build
npm run check     # tsc --noEmit
npm run lint      # eslint apps/web/src/
npm test          # vitest
```

Open http://localhost:8080/demo and start a sandbox session.

## Sandbox demo

The demo at `/demo` mints a FULL-mode sandbox session token and connects with the LiveAvatar Web SDK: avatar video, live transcriptions, and text chat (the avatar answers with voice).

Sandbox constraints (https://docs.liveavatar.com/docs/sandbox-mode):

- Only the Wayne avatar (`dd73ea75-1218-4ef3-92ce-606d5f7fbc0a`) is available
- Sessions terminate after ~1 minute
- No credit usage

For production, remove `is_sandbox`, swap in the Actinver avatar, and mint tokens from the backend instead of the dev proxy.

## Project structure

```
├── AGENTS.md              # Agent instructions index
├── GEMINI.md              # Gemini-specific rules
├── DESIGN.md              # Design token mirror for agents
├── .cursor/rules/         # Cursor agent rules
├── .agents/rules/         # Cross-IDE agent rules
├── knowledge/             # Architecture docs (read before coding)
├── apps/web/
│   ├── src/
│   │   ├── config/            # avatar + env config
│   │   ├── features/avatar/   # demo feature (components, hooks, types)
│   │   ├── routes/            # (route components live in features/, wired in router.tsx)
│   │   ├── services/          # API services (never raw fetch in components)
│   │   ├── styles/            # tokens.css + global.css (Tailwind v4)
│   │   ├── main.tsx           # entry point
│   │   └── router.tsx         # TanStack Router tree
│   └── index.html
└── services/agent/        # reserved for the agent backend
```

## Agent docs

Before working on a feature, read the relevant file in `knowledge/`. Start with `knowledge/README.md`.
