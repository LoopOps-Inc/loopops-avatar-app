# Proposal: Add Login and Splash

## Intent

`/` has no login or splash. Start mints without a password and 422s against the current backend. Users need a branded first paint, a ClientId/password gate, and a guarded `/demo`.

## Scope

### In Scope

- Timed navy/gold splash overlay on `/` (existing tokens). Skip when `prefers-reduced-motion` or a valid token exists. No `/splash`.
- Login at `/`: numeric ClientId, password, filled-dark submit. Success: `setDevAuth` then `/demo`.
- Guards: unauthenticated `/demo` → `/`; authenticated `/` → `/demo`.
- Remove InvestorSelect from StartScreen. Stop minting on Start. Login is the identity switcher.
- `mintDevToken` POSTs `{ client_id, password }` (digits as string). Add `password` to `DevTokenRequestSchema`.
- Map `UNAUTHENTICATED` and `VALIDATION_ERROR` to i18n. Do not persist the password.

### Out of Scope

Native splash/login UI; `services/agent`; `/splash` or `/login`; password persistence or `localStorage` token; re-mint or InvestorSelect on Start.

## Capabilities

### New Capabilities

- `web-auth`: splash overlay, login at `/`, token mint/storage, route guards, StartScreen identity removal, ClientId/password contract, i18n error mapping.

### Modified Capabilities

None

## Approach

Add `/` in `router.tsx`. Overlay then login; skip overlay when motion is reduced or `getDevAuth()` is valid. `/demo` `beforeLoad` requires auth; authenticated `/` redirects to `/demo`. New `features/auth/` owns LoginScreen, splash, and submit. Digit input (`inputMode="numeric"`, not `type="number"`); send trimmed string. Reuse `dev-auth.ts` and `AppShell`. Start keeps the session CTA; drop picker wiring and Start mint. Update `InvestorPicker` tests. i18n in `es.json`/`en.json`. Do not change `services/agent` or Vite proxy injection.

## Affected Areas

- Modified: `router.tsx`; `advisor-service.ts` (+ test); `packages/contracts` (`DevTokenRequestSchema`); `StartScreen` / `LiveSessionScreen` (+ tests); `InvestorPicker` (+ test); `es.json`/`en.json`
- New: `apps/web/src/features/auth/` (LoginScreen, splash, submit)
- Unchanged: `dev-auth.ts` (token only); `AppShell`; `apps/native` (WebView `/`); `services/agent`

## Risks

- Vite proxy injects a bearer when Authorization is missing (Med): client-only guard, not product auth.
- Numeric ClientId blocks aliases (`cl_demo_moderado`) (Med): spec digits (`200001`).
- Review budget near 400 authored lines (Med): `sdd-tasks` forecasts chained PRs.

## Rollback Plan

Revert the frontend and contracts commits. `/demo` returns to unguarded Start with InvestorSelect. Schema drops `password`. Agent stays as-is.

## Dependencies

Backend `POST /v1/auth/dev-token` requires password (commit `c4e620af`). Reuse `setDevAuth`/`getDevAuth`, tokens, `AppShell`, i18n.

## Success Criteria

- [ ] Unauthenticated `/` shows splash then login; skip on reduced motion or valid token.
- [ ] Valid credentials store via `setDevAuth` and land on `/demo`.
- [ ] Unauthenticated `/demo` → `/`. Authenticated `/` → `/demo`.
- [ ] StartScreen has no InvestorSelect and does not mint.
- [ ] Request body and `DevTokenRequestSchema` include `password`; ClientId is a digit string.
- [ ] `UNAUTHENTICATED` and `VALIDATION_ERROR` map to i18n; password is not persisted.
- [ ] Native WebView still loads `/`. `services/agent` is unchanged.
