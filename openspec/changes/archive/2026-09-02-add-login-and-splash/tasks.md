# Tasks: Add Login and Splash

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 450–550 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: size-exception
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Password mint contract | PR 1 (base = feature/tracker) | `npm run test -w apps/web -- src/services/advisor-service.test.ts` | N/A: unit only; no web e2e | Revert `packages/contracts/src/index.ts`, `apps/web/src/services/advisor-service.ts`, `apps/web/src/services/advisor-service.test.ts` |
| 2 | Login splash UI | PR 2 (base = PR 1 branch) | `npm run test -w apps/web -- src/features/auth` | N/A: RTL/jsdom; no web e2e | Delete `apps/web/src/features/auth/`; revert `apps/web/src/i18n/translations/es.json` and `en.json` |
| 3 | Guards + Start identity | PR 3 (base = PR 2 branch) | `npm run test -w apps/web -- src/router.test.tsx src/features/avatar/components/LiveSessionScreen.test.tsx src/features/avatar/components/InvestorPicker.test.tsx` | N/A: no web e2e; native URI stays the demo route | Revert `apps/web/src/router.tsx`, `apps/web/src/router.test.tsx`, Start/LiveSession/InvestorPicker sources and tests |

Leave `services/agent` (read-only), `apps/web/vite.config.ts` (read-only), `apps/native` (read-only).

## Phase 1: Foundation

- [x] 1.1 Add required `password` to `DevTokenRequestSchema` in `packages/contracts/src/index.ts`.
- [x] 1.2 Change `mintDevToken` in `apps/web/src/services/advisor-service.ts` to `(clientId, password)` posting `{ client_id, password }`.
- [x] 1.3 Update `apps/web/src/services/advisor-service.test.ts` so the mint body includes `password` and digit `client_id`.

## Phase 2: Auth UI

- [x] 2.1 Add `auth.*` keys (`error_unauthenticated`, `error_validation`, `error_unknown`, form labels) to `apps/web/src/i18n/translations/es.json` and `apps/web/src/i18n/translations/en.json`.
- [x] 2.2 Create `apps/web/src/features/auth/components/SplashOverlay.tsx`: 1500ms `bg-filled-dark` overlay with gold TinoMark; skip when `prefers-reduced-motion`.
- [x] 2.3 Create `apps/web/src/features/auth/hooks/use-login-submit.ts`: trim; digit-only ClientId before fetch; mint; `setDevAuth` via `apps/web/src/services/dev-auth.ts` (read-only); navigate to the demo route; map UNAUTHENTICATED and VALIDATION_ERROR; password stays in React state.
- [x] 2.4 Create `apps/web/src/features/auth/components/LoginScreen.tsx` using `apps/web/src/components/AppShell.tsx` (read-only): overlay then form; numeric inputMode; filled-dark submit; empty/alias ClientId does not mint.
- [x] 2.5 Create `apps/web/src/features/auth/components/LoginScreen.test.tsx`: splash then login; reduced-motion skip; valid-token skip overlay; 200001 mint; alias/empty no mint; success stores token and opens the demo route; failed mint stays; error i18n; password not persisted.

## Phase 3: SPA Guard RED Tests then Router

- [x] 3.1 Add failing `apps/web/src/router.test.tsx`: no getDevAuth, opening the demo route lands on the login route.
- [x] 3.2 Same file: stored token, opening the login route lands on the demo route.
- [x] 3.3 Same file: expiresAt in the past, opening the demo route lands on the login route.
- [x] 3.4 Same file: native deep-link to the demo route uses that same redirect; native URI stays the demo route.
- [x] 3.5 Modify `apps/web/src/router.tsx`: lazy login route for LoginScreen; beforeLoad via getDevAuth; unauthenticated demo route redirects to login; authenticated login route redirects to demo.

## Phase 4: Session Start Identity

- [x] 4.1 Remove InvestorSelect, mint, and `useInvestors` from `apps/web/src/features/avatar/components/StartScreen.tsx`; keep the session CTA.
- [x] 4.2 Stop Start mint and picker wiring in `apps/web/src/features/avatar/components/LiveSessionScreen.tsx`.
- [x] 4.3 Stop remint in `apps/web/src/features/avatar/components/InvestorPicker.tsx`.
- [x] 4.4 Update `apps/web/src/features/avatar/components/LiveSessionScreen.test.tsx`: no picker; start and repeat start send no mint.
- [x] 4.5 Update `apps/web/src/features/avatar/components/InvestorPicker.test.tsx` so remint no longer runs.
