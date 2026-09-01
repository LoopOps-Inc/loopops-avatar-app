---
trigger: always_on
---

To ensure high code quality, AI agents and developers MUST adhere to the following rules:

1. **No raw fetches in components:** All network calls MUST live in `src/services/` and use a shared API client. Components call hooks or services, never `fetch` directly.

2. **Design tokens only:** Never hardcode hex colors or magic spacing in components. Import from `src/theme/tokens.ts` or use `getTheme()`.

3. **Clean UI rendering:** When editing JSX/TSX, ensure no accidental text characters or typos are left outside React tags.

4. **Feature modules:** New features go under `src/features/<name>/` with `components/`, `hooks/`, `services/`, and `types/` as needed.

5. **i18n for copy:** User-facing strings use `t('namespace.key')` once i18n is set up. Copy follows `knowledge/writing-style.md`.
