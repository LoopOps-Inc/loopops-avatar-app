# Apply Progress: add-login-and-splash

**Change**: add-login-and-splash
**Mode**: Standard (strict_tdd: false)
**Delivery**: size:exception (maintainer accepted). Chain strategy: size-exception. All tasks 1.1–4.5 in one batch on `feature/login`.
**Status**: 18/18 tasks complete

## Work Unit Evidence

| Unit                      | Focused test command                                                                                                                                               | Result                   | Runtime harness                                                             | Rollback boundary                                                                                                                     |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------ | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 1 Password mint contract  | `npm run test -w apps/web -- src/services/advisor-service.test.ts`                                                                                                 | pass — 1 file, 13 tests  | N/A: unit only; no web e2e in this workspace                                | Revert `packages/contracts/src/index.ts`, `apps/web/src/services/advisor-service.ts`, `apps/web/src/services/advisor-service.test.ts` |
| 2 Login splash UI         | `npm run test -w apps/web -- src/features/auth`                                                                                                                    | pass — 1 file, 10 tests  | N/A: RTL/jsdom; no web e2e                                                  | Delete `apps/web/src/features/auth/`; revert `apps/web/src/i18n/translations/es.json` and `en.json`                                   |
| 3 Guards + Start identity | `npm run test -w apps/web -- src/router.test.tsx src/features/avatar/components/LiveSessionScreen.test.tsx src/features/avatar/components/InvestorPicker.test.tsx` | pass — 3 files, 18 tests | N/A: no web e2e; native WebView URI stays `/demo` (`apps/native` unchanged) | Revert `apps/web/src/router.tsx`, `apps/web/src/router.test.tsx`, Start/LiveSession/InvestorPicker sources and tests                  |

Workspace follow-up after focused suites: `npm run test -w apps/web` pass (14 files, 79 tests); `npm run check -w apps/web` pass (`tsc --noEmit`).

SPA guard tests 3.1–3.4 were written before router production change 3.5 (`createAppRouter` + `beforeLoad` via `getDevAuth()`).

## Completed Tasks

- [x] 1.1–1.3 Password on `DevTokenRequestSchema`; `mintDevToken(clientId, password)` posts `{ client_id, password }`
- [x] 2.1–2.5 `auth.*` i18n; SplashOverlay; useLoginSubmit; LoginScreen; LoginScreen tests
- [x] 3.1–3.5 Router guards and RED tests; lazy `/` login
- [x] 4.1–4.5 StartScreen/LiveSessionScreen drop picker and mint; InvestorPicker stops remint; tests updated

## Deviations from Design

None — implementation matches design. `createAppRouter()` was extracted from `router.tsx` so SPA guard tests can inject memory history. Native WebView URI remains `/demo`.

## Issues Found

None remaining. LoginScreen tests mock `useNavigate` instead of mounting a second RouterProvider (jsdom render was empty before the route loaded). Repeat-start test resets live-session `endReason` before the second start so SessionPanel does not immediately end.
