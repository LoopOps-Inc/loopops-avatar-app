---
name: LoopOps Avatar
description: Actinver talking-head avatar web app design system
version: '2.0'
source: ../loopops-web-app/DESIGN.md

colors:
  neutral-0: '#ffffff'
  brand-ink: '#041e41'
  brand-gold: '#927b2f'
  brand-gold-bright: '#f0ca4d'
  gray-chat-bg: '#f7f8fa'
  gray-chat-border: '#e2e4e9'
  gray-chat-border-soft: '#ebebeb'
  gray-chat-meta: '#4b5563'
  gray-chat-date: '#6d7382'
  gray-chat-placeholder: '#9398a5'
  chat-agent-bg: '#fffdf5'
  chat-text-small: '#6082b6'
  actinver-submit-bg: '#041e41'
  actinver-submit-fg: '#f0ca4d'
  success-50: '#31a147'
  error-50: '#c53f3f'
  warning-50: '#a48823'
  info-50: '#6581d9'

typography:
  heading:
    fontFamily: 'Funnel Display, sans-serif'
  body:
    fontFamily: "Public Sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
  xs: 8
  sm: 11
  md: 12
  base: 14
  lg: 16
  xl: 18
  2xl: 20
  3xl: 24
  4xl: 32

rounded:
  xs: 8
  sm: 16
  md: 24
  lg: 32
  cta: 26.5
  bubble: 20
  tail: 4
  full: 999

spacing:
  '1': 4
  '2': 8
  '3': 12
  '4': 16
  '5': 20
  '6': 24
  '7': 28
  '8': 32
  '10': 40
  '12': 48
  '16': 64
  '20': 80
  '24': 96

components:
  filled-dark:
    backgroundColor: '{colors.brand-ink}'
    textColor: '{colors.neutral-0}'
  advisor-submit:
    backgroundColor: '{colors.actinver-submit-bg}'
    textColor: '{colors.actinver-submit-fg}'
---

# LoopOps Avatar Design System

Agent-readable token mirror. Code implementation: `apps/web/src/styles/tokens.css` (primitives) + `apps/web/src/styles/global.css` (semantic mapping and Tailwind wiring).

This file lists only the tokens the app uses. The upstream **loopops-web-app** palette is larger. Port a token from there when a screen needs it, adding it to `tokens.css` first, then to `@theme inline` in `global.css`, then here. See `knowledge/design-system.md` for usage rules.

## Theme

Light only. There is no `.dark` class and no `prefers-color-scheme` switching. `color-scheme: light` is set on `html` in `global.css`.

## Primary color rule

Primary CTAs use **filled-dark** (`bg-filled-dark`), not brand blue. There is no accent blue token in the app right now; add `brand-accent-50` (`#0431c0`) back if a screen needs links or brand accents.

Advisor send buttons use `bg-advisor-submit` with gold text (`text-advisor-submit-fg`).

## Semantic mapping

| Semantic          | Tailwind class                | Primitive             |
| ----------------- | ----------------------------- | --------------------- |
| surface           | `bg-surface`                  | neutral-0             |
| surface-sub       | `bg-surface-sub`              | gray-chat-bg          |
| content           | `text-content`                | brand-ink             |
| content-sub       | `text-content-sub`            | gray-chat-meta        |
| content-muted     | `text-content-muted`          | gray-chat-placeholder |
| content-small     | `text-content-small`          | chat-text-small       |
| content-faint     | `text-content-faint`          | gray-chat-date        |
| icon-muted        | `text-icon-muted`             | gray-chat-placeholder |
| filled-dark       | `bg-filled-dark`              | brand-ink             |
| filled-dark-fg    | `text-filled-dark-fg`         | neutral-0             |
| outline           | `border-outline`              | gray-chat-border      |
| outline-soft      | `border-outline-soft`         | gray-chat-border-soft |
| chat-user         | `bg-chat-user`                | brand-ink             |
| chat-user-fg      | `text-chat-user-fg`           | neutral-0             |
| chat-agent        | `bg-chat-agent`               | chat-agent-bg         |
| chat-agent-border | `border-chat-agent-border`    | brand-gold-bright     |
| advisor-submit    | `bg-advisor-submit`           | actinver-submit-bg    |
| advisor-submit-fg | `text-advisor-submit-fg`      | actinver-submit-fg    |
| success           | `text-success` / `bg-success` | success-50            |
| error             | `text-error` / `bg-error`     | error-50              |
| warning           | `text-warning` / `bg-warning` | warning-50            |
| info              | `text-info` / `bg-info`       | info-50               |

`--brand-gold` (`#927b2f`) has no semantic alias. It is used directly for the agent avatar ring in `ChatBubble.tsx` via `border-(--brand-gold)`.
