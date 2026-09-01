---
title: Design System
scope: ui
last-updated: 2026-09-01
source: ../loopops-web-app/knowledge/design-system.md
---

# Design System

## Overview

Ported from **loopops-web-app** for brand consistency across LoopOps and Actinver avatar experiences. Implemented in React Native via `src/theme/tokens.ts` instead of Tailwind.

**Spacing:** 4px grid (`spacing[1]` = 4px through `spacing[8]` = 32px).

**Typography:** Funnel Display (headings), Public Sans (body). Load custom fonts when added to the project.

## Checklist — every component and screen

1. **Tokens first** — import from `src/theme/tokens.ts`, never hardcode hex
2. **i18n always** — every user-facing string uses `t('namespace.key')`
3. **Theme-aware** — use `getTheme(isDarkMode)` semantic colors

## Primary color rule — MANDATORY

> **The primary action color is BLACK (filled-dark), not blue.**

- Primary buttons: `theme.colors.filledDark` + `theme.colors.filledDarkFg`
- `filledDark` = `#2F2F2F` light / `#F0F0F0` dark
- Brand blue `#0431C0` is for links, accents, and brand moments only

```tsx
// ✅ Primary action
<Pressable style={{ backgroundColor: theme.colors.filledDark }}>
  <Text style={{ color: theme.colors.filledDarkFg }}>Confirmar</Text>
</Pressable>

// ❌ Never use accent blue for primary CTAs
<Pressable style={{ backgroundColor: theme.colors.accent }}>
```

## Semantic colors

| Token | Light | Use for |
| ----- | ----- | ------- |
| `surface` | `#FFFFFF` | Main backgrounds |
| `surfaceSub` | `#F5F5F5` | Secondary panels |
| `content` | `#0F0F0F` | Primary text |
| `contentSub` | `#525252` | Secondary text |
| `contentMuted` | `#BEBEBE` | Placeholders |
| `accent` | `#0431C0` | Brand links, highlights |
| `outline` | `#EEEEEE` | Borders |
| `success` | `#31A147` | Positive status |
| `error` | `#C53F3F` | Error status |
| `warning` | `#A48823` | Warning status |

Dark mode inverts surface/content via `getTheme(true)`.

## Risk tier colors (investment UI)

| Tier | Token | Color |
| ---- | ----- | ----- |
| Low | `success` | Green |
| Medium | `warning` | Yellow/amber |
| High | `error` | Red |

## Border radius

| Token | Value | Use |
| ----- | ----- | --- |
| `radius.xs` | 8 | Cards, inputs |
| `radius.sm` | 16 | Containers |
| `radius.md` | 24 | Modals |
| `radius.cta` | 26.5 | CTA buttons |
| `radius.full` | 999 | Pills, avatars |

## Agent / avatar element colors

`element1` through `element5` for distinct agent or portfolio segment colors (from LoopOps design system).

## Gotchas

- React Native `StyleSheet.create` is static; use dynamic styles from `getTheme()` for theme-dependent colors.
- Touch targets: minimum 44×44 pt for accessibility.
- Test light and dark mode on both iOS and Android.
- Full token reference: `DESIGN.md` and `src/theme/tokens.ts`.
