---
name: LoopOps Avatar
description: Actinver talking-head avatar web app design system
version: '1.1'
source: ../loopops-web-app/DESIGN.md

colors:
  neutral-0: '#ffffff'
  neutral-5: '#fafafa'
  neutral-10: '#f5f5f5'
  neutral-15: '#f0f0f0'
  neutral-20: '#eeeeee'
  neutral-30: '#e2e2e2'
  neutral-40: '#bebebe'
  neutral-50: '#9a9a9a'
  neutral-55: '#7d7d7d'
  neutral-60: '#525252'
  neutral-70: '#2f2f2f'
  neutral-80: '#1a1a1a'
  neutral-90: '#0f0f0f'
  brand-accent-50: '#0431c0'
  brand-accent-60: '#021d73'
  success-50: '#31a147'
  error-50: '#c53f3f'
  warning-50: '#a48823'
  element-1: '#306ee1'
  element-2: '#40ad82'
  element-3: '#dd9b25'
  element-4: '#e7823f'
  element-5: '#d856a8'
  brand-ink: '#041e41'
  brand-gold-bright: '#f0ca4d'
  chat-agent-bg: '#fffdf5'
  chat-text-small: '#6082b6'
  gray-chat-placeholder: '#9398a5'
  primary: '#0431c0'

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
  xs-inner: 6
  sm: 16
  md: 24
  lg: 32
  cta: 26.5
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
    backgroundColor: '{colors.neutral-70}'
    textColor: '{colors.neutral-5}'
  accent:
    backgroundColor: '{colors.brand-accent-50}'
    textColor: '{colors.neutral-0}'
---

# LoopOps Avatar Design System

Agent-readable token mirror. Code implementation: `apps/web/src/styles/tokens.css` (primitives) + `apps/web/src/styles/global.css` (semantic mapping and Tailwind wiring).

Synced from **loopops-web-app** `DESIGN.md` v1.1. See `knowledge/design-system.md` for usage rules.

## Primary color rule

Primary CTAs use **filled-dark** (`bg-filled-dark`), not brand blue. Blue is for links and accents only.

Advisor navy send buttons use `bg-advisor-submit` with gold text (`text-advisor-submit-fg`). Gold chips keep navy text (`bg-advisor-cta` / `text-advisor-cta-fg`).

## Semantic mapping

| Semantic          | Tailwind class             | Light                 | Dark              |
| ----------------- | -------------------------- | --------------------- | ----------------- |
| surface           | `bg-surface`               | neutral-0             | neutral-70        |
| surface-sub       | `bg-surface-sub`           | gray-chat-bg          | neutral-80        |
| content           | `text-content`             | brand-ink             | neutral-5         |
| content-sub       | `text-content-sub`         | gray-chat-meta        | neutral-20        |
| content-muted     | `text-content-muted`       | gray-chat-placeholder | neutral-40        |
| content-small     | `text-content-small`       | chat-text-small       | chat-text-small   |
| icon-muted        | `text-icon-muted`          | gray-chat-placeholder | inherit           |
| filled-dark       | `bg-filled-dark`           | brand-ink             | neutral-15        |
| outline           | `border-outline`           | gray-chat-border      | neutral-60        |
| accent            | `bg-accent`                | brand-accent-50       | brand-accent-50   |
| chat-user         | `bg-chat-user`             | brand-ink             | brand-ink         |
| chat-user-fg      | `text-chat-user-fg`        | neutral-0             | neutral-0         |
| chat-agent        | `bg-chat-agent`            | chat-agent-bg         | chat-agent-bg     |
| chat-agent-border | `border-chat-agent-border` | brand-gold-bright     | brand-gold-bright |
| advisor-cta       | `bg-advisor-cta`           | brand-gold-bright     | brand-gold-bright |
| advisor-cta-fg    | `text-advisor-cta-fg`      | brand-ink             | brand-ink         |
| advisor-submit    | `bg-advisor-submit`        | brand-ink             | brand-ink         |
| advisor-submit-fg | `text-advisor-submit-fg`   | brand-gold-bright     | brand-gold-bright |

Dark mode inverts via `.dark` class on the root element (see `apps/web/src/styles/global.css`).
