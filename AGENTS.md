# Agent instructions — LoopOps Avatar App

Shared rules for **Cursor**, **GitHub Copilot**, **Claude Code**, **Gemini**, and other coding agents.

## Primary docs

| Audience | File |
| -------- | ---- |
| All agents | This file + `knowledge/` |
| Cursor | `.cursor/rules/*.mdc` |
| Gemini CLI / Gemini Assist | `GEMINI.md` |
| Design tokens (agents) | `DESIGN.md` |
| Design tokens (code) | `src/theme/tokens.ts` |

## Project scope

React Native mobile app for **Actinver** talking-head avatar:

- **HeyGen Live Avatar** for video/voice output ([docs.liveavatar.com](https://docs.liveavatar.com/))
- **Custom backend** (Python or TypeScript) with LangChain / LangGraph + **Gemini**
- **Two interaction modes**: chat (typed) and conversation (voice)
- Investment portfolio Q&A, product recommendations, and guided invest/retire/sell flows

Sibling repos for reference only (do not copy web-specific rules blindly):

- `../loopops-web-app` — canonical design tokens, writing style, chat patterns
- `../loopops-website` — marketing site; ignore stale `.agent/rules/`

## Knowledge base — always consult `knowledge/`

**Before working on any feature, read the relevant doc in [`knowledge/`](./knowledge/).** The index lives at [`knowledge/README.md`](./knowledge/README.md). Every doc follows **Context → Architecture → Patterns → Gotchas**.

When a rule should be encoded for agents, document it in `knowledge/`, not in ad-hoc instruction files.

## Mandatory rules

### Design tokens — no hardcoded colors

Use `src/theme/tokens.ts` and semantic theme colors. Never scatter hex values in components.

```tsx
import { getTheme } from './src/theme';

const theme = getTheme(isDarkMode);
// theme.colors.surface, theme.colors.content, theme.colors.filledDark
```

Primary CTA buttons use **filled-dark** (`#2F2F2F` light / `#F0F0F0` dark), not brand blue. Blue (`#0431C0`) is for links and brand accents only.

### API calls — service layer only

Never use raw `fetch` in components. Place network calls in `src/services/` with a shared client wrapper.

### i18n — every user-facing string

All copy goes through i18n (`t('namespace.key')`). Add keys to both `es` and `en` when i18n is wired up.

Copy follows [`knowledge/writing-style.md`](./knowledge/writing-style.md): direct, professional, no AI filler, no em dashes, no emojis.

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

Shared theme: `src/theme/`. Shared services: `src/services/`.
