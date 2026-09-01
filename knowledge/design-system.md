---
title: Design System
scope: ui
last-updated: 2026-09-01
source: ../loopops-web-app/knowledge/design-system.md
---

# Design System

## Overview

Ported from **loopops-web-app** for brand consistency across LoopOps and Actinver avatar experiences. Implemented with **Tailwind CSS v4**: primitives in `apps/web/src/styles/tokens.css`, semantic mapping and `@theme inline` wiring in `apps/web/src/styles/global.css`.

**Spacing:** 4px grid (Tailwind default scale aligns).

**Typography:** Funnel Display (headings), Public Sans (body). Loaded in `index.html`.

## Checklist — every component and screen

1. **Tokens first** — use semantic Tailwind utilities (`bg-surface`, `text-content-sub`...), never hardcode hex
2. **i18n always** — every user-facing string uses `t('namespace.key')` (pending i18n wiring)
3. **Theme-aware** — semantic classes flip automatically in dark mode via the `.dark` class

## Primary color rule — MANDATORY

> **The primary action color is BLACK (filled-dark), not blue.**

- Primary buttons: `bg-filled-dark` + `text-filled-dark-fg` (+ `rounded-cta`)
- `filled-dark` = `#041E41` light / `#F0F0F0` dark
- Advisor send buttons use `bg-advisor-submit` + `text-advisor-submit-fg` (navy + gold)
- Gold chips keep navy text: `bg-advisor-cta` + `text-advisor-cta-fg`
- Brand blue `#0431C0` is for links, accents, and brand moments only

```tsx
// ✅ Primary action
<button className="rounded-cta bg-filled-dark px-6 py-2 text-filled-dark-fg">Confirmar</button>

// ❌ Never use accent blue for primary CTAs
<button className="rounded-cta bg-accent px-6 py-2 text-accent-fg">Confirmar</button>
```

## Semantic utilities

| Class                                          | Light                 | Use for                            |
| ---------------------------------------------- | --------------------- | ---------------------------------- |
| `bg-surface` / `text-content`                  | `#FFFFFF` / `#041E41` | Main backgrounds and text          |
| `bg-surface-sub`                               | `#F7F8FA`             | Secondary panels                   |
| `text-content-sub`                             | `#4B5563`             | Secondary body text                |
| `text-content-muted`                           | `#9398A5`             | Placeholders                       |
| `text-content-small`                           | `#6082B6`             | Timestamps, captions, fine print   |
| `text-icon-muted`                              | `#9398A5`             | Decorative icons                   |
| `bg-filled-dark` + `text-filled-dark-fg`       | `#041E41` / `#FFFFFF` | Dark surfaces                      |
| `bg-advisor-submit` + `text-advisor-submit-fg` | `#041E41` / `#F0CA4D` | Navy send buttons (gold icon/text) |
| `bg-advisor-cta` + `text-advisor-cta-fg`       | `#F0CA4D` / `#041E41` | Gold chips and gold icon buttons   |
| `bg-chat-user` + `text-chat-user-fg`           | `#041E41` / `#FFFFFF` | User chat bubbles                  |
| `bg-chat-agent` + `border-chat-agent-border`   | `#FFFDF5` / `#F0CA4D` | Agent chat bubbles                 |
| `text-accent` / `bg-accent`                    | `#0431C0`             | Brand links, highlights            |
| `border-outline`                               | `#E2E4E9`             | Borders                            |
| `text-success` / `bg-success`                  | `#31A147`             | Positive status                    |
| `text-error` / `bg-error`                      | `#C53F3F`             | Error status                       |
| `text-warning` / `bg-warning`                  | `#A48823`             | Warning status                     |

Dark mode inverts surface/content via the `.dark` class on a root element. Use `.light` on a subtree when a screen must stay white/black regardless of system theme.

## Chat bubbles

| Role      | Classes                                         | Colors                 |
| --------- | ----------------------------------------------- | ---------------------- |
| User      | `bg-chat-user text-chat-user-fg`                | Navy `#041E41` / white |
| Agent     | `bg-chat-agent border-chat-agent-border border` | Cream `#FFFDF5` / gold |
| Timestamp | `text-content-small`                            | `#6082B6`              |

Do not reuse `bg-filled-dark` for user bubbles. Chat tokens stay independent of CTA surfaces.

## Risk tier colors (investment UI)

| Tier   | Utility        | Color        |
| ------ | -------------- | ------------ |
| Low    | `text-success` | Green        |
| Medium | `text-warning` | Yellow/amber |
| High   | `text-error`   | Red          |

## Border radius

| Tailwind class | Value  | Use            |
| -------------- | ------ | -------------- |
| `rounded-xs`   | 8px    | Cards, inputs  |
| `rounded-sm`   | 16px   | Containers     |
| `rounded-md`   | 24px   | Modals         |
| `rounded-cta`  | 26.5px | CTA buttons    |
| `rounded-full` | 999px  | Pills, avatars |

## Agent / avatar element colors

`--element-1` through `--element-5` in `tokens.css` for distinct agent or portfolio segment colors (from LoopOps design system).

## Gotchas

- Tailwind v4 theme values are wired with `@theme inline` in `global.css`; add new tokens as CSS variables in `tokens.css` first, then map them.
- Touch targets: minimum 44×44 px (`min-h-11`) for accessibility on mobile.
- Dark mode is system-driven (`prefers-color-scheme`, FOUC script in `index.html`) with no visible toggle for now; the semantic classes flip automatically. Test both themes.
- Icons come from `lucide-react` (same family as loopops-web-app). Never use emojis as icons.
- Full token reference: `DESIGN.md`.
