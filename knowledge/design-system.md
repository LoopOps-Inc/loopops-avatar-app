---
title: Design System
scope: ui
last-updated: 2026-09-01
source: ../loopops-web-app/knowledge/design-system.md
---

# Design System

## Overview

Ported from **loopops-web-app** for brand consistency across LoopOps and Actinver avatar experiences. Implemented with **Tailwind CSS v4**: primitives in `src/styles/tokens.css`, semantic mapping and `@theme inline` wiring in `src/styles/global.css`.

**Spacing:** 4px grid (Tailwind default scale aligns).

**Typography:** Funnel Display (headings), Public Sans (body). Loaded in `index.html`.

## Checklist — every component and screen

1. **Tokens first** — use semantic Tailwind utilities (`bg-surface`, `text-content-sub`...), never hardcode hex
2. **i18n always** — every user-facing string uses `t('namespace.key')` (pending i18n wiring)
3. **Theme-aware** — semantic classes flip automatically in dark mode via the `.dark` class

## Primary color rule — MANDATORY

> **The primary action color is BLACK (filled-dark), not blue.**

- Primary buttons: `bg-filled-dark` + `text-filled-dark-fg` (+ `rounded-cta`)
- `filled-dark` = `#2F2F2F` light / `#F0F0F0` dark
- Brand blue `#0431C0` is for links, accents, and brand moments only

```tsx
// ✅ Primary action
<button className="rounded-cta bg-filled-dark px-6 py-2 text-filled-dark-fg">Confirmar</button>

// ❌ Never use accent blue for primary CTAs
<button className="rounded-cta bg-accent px-6 py-2 text-accent-fg">Confirmar</button>
```

## Semantic utilities

| Class                                    | Light                 | Use for                   |
| ---------------------------------------- | --------------------- | ------------------------- |
| `bg-surface` / `text-content`            | `#FFFFFF` / `#0F0F0F` | Main backgrounds and text |
| `bg-surface-sub`                         | `#F5F5F5`             | Secondary panels          |
| `text-content-sub`                       | `#525252`             | Secondary text            |
| `text-content-muted`                     | `#BEBEBE`             | Placeholders              |
| `bg-filled-dark` + `text-filled-dark-fg` | `#2F2F2F` / `#FAFAFA` | Primary CTAs              |
| `text-accent` / `bg-accent`              | `#0431C0`             | Brand links, highlights   |
| `border-outline`                         | `#EEEEEE`             | Borders                   |
| `text-success` / `bg-success`            | `#31A147`             | Positive status           |
| `text-error` / `bg-error`                | `#C53F3F`             | Error status              |
| `text-warning` / `bg-warning`            | `#A48823`             | Warning status            |

Dark mode inverts surface/content via the `.dark` class on a root element.

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
