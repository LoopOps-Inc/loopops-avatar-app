---
title: Design System
scope: ui
last-updated: 2026-09-01
source: ../loopops-web-app/knowledge/design-system.md
---

# Design System

## Overview

Ported from **loopops-web-app** for brand consistency across LoopOps and Actinver avatar experiences. Implemented with **Tailwind CSS v4**: primitives in `apps/web/src/styles/tokens.css`, semantic mapping and `@theme inline` wiring in `apps/web/src/styles/global.css`.

Only the tokens the app uses are kept in `tokens.css`. The upstream palette is larger, so port what you need instead of hardcoding a hex.

**Spacing:** 4px grid (Tailwind default scale aligns).

**Typography:** Funnel Display for headings (`font-heading`, applied automatically to `h1`–`h3`), Public Sans for body. Families are declared in `global.css`, web fonts are loaded in `index.html`. Both families must stay in sync: a family named in `global.css` but missing from the Google Fonts link silently falls back to system sans.

**Theme:** light only. There is no dark mode and no theme toggle.

## Checklist — every component and screen

1. **Tokens first** — use semantic Tailwind utilities (`bg-surface`, `text-content-sub`...), never hardcode hex
2. **i18n always** — every user-facing string uses `t('namespace.key')`
3. **New color?** — add the primitive to `tokens.css`, map it in `global.css`, then record it in `DESIGN.md`

## Primary color rule — MANDATORY

> **The primary action color is navy (filled-dark), not blue.**

- Primary buttons: `bg-filled-dark` + `text-filled-dark-fg`
- `filled-dark` = `#041E41`
- Advisor send buttons use `bg-advisor-submit` + `text-advisor-submit-fg` (navy + gold)
- There is no accent blue token today. Add `brand-accent-50` (`#0431C0`) back to `tokens.css` and `global.css` when a screen needs links or brand accents

```tsx
// ✅ Primary action
<button className="rounded-cta bg-filled-dark px-6 py-2 text-filled-dark-fg">Confirmar</button>

// ❌ Hardcoded hex
<button className="rounded-[26.5px] bg-[#041e41] px-6 py-2 text-white">Confirmar</button>
```

## Semantic utilities

| Class                                          | Value                 | Use for                              |
| ---------------------------------------------- | --------------------- | ------------------------------------ |
| `bg-surface` / `text-content`                  | `#FFFFFF` / `#041E41` | Main backgrounds and text            |
| `bg-surface-sub`                               | `#F7F8FA`             | Secondary panels, inputs, skeletons  |
| `text-content-sub`                             | `#4B5563`             | Secondary body text                  |
| `text-content-muted`                           | `#9398A5`             | Placeholders                         |
| `text-content-small`                           | `#6082B6`             | Captions, section labels, fine print |
| `text-content-faint`                           | `#6D7382`             | Chat timestamps                      |
| `text-icon-muted`                              | `#9398A5`             | Decorative icons                     |
| `bg-filled-dark` + `text-filled-dark-fg`       | `#041E41` / `#FFFFFF` | Primary CTAs and dark surfaces       |
| `bg-advisor-submit` + `text-advisor-submit-fg` | `#041E41` / `#F0CA4D` | Navy send buttons (gold icon/text)   |
| `bg-chat-user` + `text-chat-user-fg`           | `#041E41` / `#FFFFFF` | User chat bubbles                    |
| `bg-chat-agent` + `border-chat-agent-border`   | `#FFFDF5` / `#F0CA4D` | Agent chat bubbles                   |
| `border-outline`                               | `#E2E4E9`             | Borders                              |
| `border-outline-soft`                          | `#EBEBEB`             | Card borders inside panels           |
| `text-success` / `bg-success`                  | `#31A147`             | Positive status                      |
| `text-error` / `bg-error`                      | `#C53F3F`             | Error status                         |
| `text-warning` / `bg-warning`                  | `#A48823`             | Warning status                       |
| `text-info` / `bg-info`                        | `#6581D9`             | Informational notes                  |

Tint and border variants come from opacity modifiers on the same token, for example `bg-error/10` with `border-error/30` for an error banner.

## Chat bubbles

| Role      | Classes                                         | Colors                 |
| --------- | ----------------------------------------------- | ---------------------- |
| User      | `bg-chat-user text-chat-user-fg`                | Navy `#041E41` / white |
| Agent     | `bg-chat-agent border-chat-agent-border border` | Cream `#FFFDF5` / gold |
| Timestamp | `text-content-faint`                            | `#6D7382`              |

Do not reuse `bg-filled-dark` for user bubbles. Chat tokens stay independent of CTA surfaces.

The agent avatar ring uses `--brand-gold` (`#927B2F`) directly: `border-(--brand-gold)`. It is the one primitive with no semantic alias.

## Risk tier colors (investment UI)

| Tier   | Utility        | Color        |
| ------ | -------------- | ------------ |
| Low    | `text-success` | Green        |
| Medium | `text-warning` | Yellow/amber |
| High   | `text-error`   | Red          |

## Border radius

| Tailwind class   | Value  | Use                          |
| ---------------- | ------ | ---------------------------- |
| `rounded-xs`     | 8px    | Banners, small cards         |
| `rounded-sm`     | 16px   | Containers                   |
| `rounded-md`     | 24px   | Modals                       |
| `rounded-lg`     | 32px   | Desktop session frame        |
| `rounded-cta`    | 26.5px | CTA buttons                  |
| `rounded-bubble` | 20px   | Chat bubbles                 |
| `rounded-tail`   | 4px    | Agent bubble tail corner     |
| `rounded-full`   | pill   | Pills, avatars, icon buttons |

## Gotchas

- Tailwind v4 theme values are wired with `@theme inline` in `global.css`; add new tokens as CSS variables in `tokens.css` first, then map them.
- A class like `bg-gray-chat-bg` silently renders nothing. Primitives are not Tailwind colors, only the names mapped in `@theme inline` are.
- Touch targets: minimum 44×44 px (`min-h-11`) for accessibility on mobile.
- Icons come from `lucide-react` (same family as loopops-web-app). Never use emojis as icons.
- Full token reference: `DESIGN.md`.
