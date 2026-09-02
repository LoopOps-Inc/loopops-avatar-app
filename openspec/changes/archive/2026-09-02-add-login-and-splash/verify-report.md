```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:6a6ad5f6768aa878f53a09774b7c54c74ee900d36c61fb2e6869cdd38e0ea0f4
verdict: pass
blockers: 0
critical_findings: 0
requirements: 6/6
scenarios: 14/14
test_command: npm run test -w apps/web
test_exit_code: 0
test_output_hash: sha256:a7d360a07dfb10fba391190851da2e702e3d9be9301ee9f3e057e1a07241739c
build_command: npm run build
build_exit_code: 0
build_output_hash: sha256:eb5f4ba45130f68b2c8c6599ec056da09dddf47905fd4360ab86d4e5a6af654e
```

## Verification Report

**Change**: add-login-and-splash
**Version**: N/A
**Mode**: Standard

### Completeness

| Metric           | Value |
| ---------------- | ----- |
| Tasks total      | 18    |
| Tasks complete   | 18    |
| Tasks incomplete | 0     |

### Build & Tests Execution

**Build**: Passed

```text
npm run check -w apps/web  (exit 0, tsc --noEmit)
npm run build              (exit 0, tsc --noEmit && vite build)

vite v8.2.2 building client environment for production...
✓ 2367 modules transformed.
dist/assets/LoginScreen-tQfkLoAC.js          3.68 kB
dist/assets/LiveSessionScreen-B-_BOmVO.js  545.55 kB
✓ built in 399ms
chunk-size warning for LiveSessionScreen (>500 kB). Exit code remains 0.
```

**Tests**: 79 passed / 0 failed / 0 skipped

```text
npm run test -w apps/web  (exit 0)

 Test Files  14 passed (14)
      Tests  79 passed (79)
 Duration  3.14s
```

**Coverage**: n/a / threshold: 0% → Not available

### Spec Compliance Matrix

| Requirement                        | Scenario                             | Test                                                                                                                                                                                                     | Result    |
| ---------------------------------- | ------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| Splash overlay on entry            | Splash then login                    | `LoginScreen.test.tsx > shows a timed splash overlay then the login form`                                                                                                                                | COMPLIANT |
| Splash overlay on entry            | Reduced motion skips overlay         | `LoginScreen.test.tsx > skips the overlay when reduced motion is preferred`                                                                                                                              | COMPLIANT |
| Splash overlay on entry            | Valid token skips overlay            | `LoginScreen.test.tsx > skips the overlay when a valid token is stored`; `router.test.tsx > sends authenticated visitors from login to the demo route`                                                   | COMPLIANT |
| Login credentials and mint request | Digit ClientId submits               | `LoginScreen.test.tsx > mints with digit client_id 200001 and the entered password`; `advisor-service.test.ts > mints a dev token for the selected client_id`                                            | COMPLIANT |
| Login credentials and mint request | Alias ClientId rejected              | `LoginScreen.test.tsx > rejects an alias ClientId without minting`                                                                                                                                       | COMPLIANT |
| Login credentials and mint request | Empty credentials                    | `LoginScreen.test.tsx > does not mint when ClientId or password is empty`                                                                                                                                | COMPLIANT |
| Successful authentication          | Valid credentials land on demo       | `LoginScreen.test.tsx > stores the token, opens the demo route, and does not persist the password`                                                                                                       | COMPLIANT |
| Successful authentication          | Failed mint stays on login           | `LoginScreen.test.tsx > stays on login when mint fails`                                                                                                                                                  | COMPLIANT |
| Route guards                       | Unauthenticated demo redirects home  | `router.test.tsx > sends unauthenticated visitors from the demo route to login`; `router.test.tsx > treats an expired token as unauthenticated on the demo route`                                        | COMPLIANT |
| Route guards                       | Authenticated home redirects to demo | `router.test.tsx > sends authenticated visitors from login to the demo route`                                                                                                                            | COMPLIANT |
| Session start has no identity mint | Start session without picker         | `LiveSessionScreen.test.tsx > renders the welcome screen with a start action and no investor picker`; `LiveSessionScreen.test.tsx > starts a session through the advisor backend after the start action` | COMPLIANT |
| Session start has no identity mint | Repeat start does not mint           | `LiveSessionScreen.test.tsx > does not mint when starting a session again after the server ends it`                                                                                                      | COMPLIANT |
| Auth errors and password privacy   | Unauthenticated maps to copy         | `LoginScreen.test.tsx > stays on login when mint fails`                                                                                                                                                  | COMPLIANT |
| Auth errors and password privacy   | Validation error maps to copy        | `LoginScreen.test.tsx > maps VALIDATION_ERROR to auth copy`                                                                                                                                              | COMPLIANT |

**Compliance summary**: 14/14 scenarios compliant

Orchestrator browser check is informational only (no web e2e in this change). Splash then login was observed at `/`. Unauthenticated `/demo` redirected to `/`. Live mint was not exercised because the agent backend was not running.

### Correctness (Static Evidence)

| Requirement                        | Status      | Notes                                                                                                                                                              |
| ---------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Splash overlay on entry            | Implemented | `SplashOverlay` is a 1500ms `bg-filled-dark` overlay with gold `TinoMark`. It skips on `prefers-reduced-motion` or `skip` from `getDevAuth()`. Login stays on `/`. |
| Login credentials and mint request | Implemented | `useLoginSubmit` trims, requires `/^\d+$/`, then `mintDevToken(clientId, password)` posts `{ client_id, password }`. Alias and empty inputs return before fetch.   |
| Successful authentication          | Implemented | Success calls `setDevAuth` with token fields only, clears password state, and navigates to `/demo`. Catch path does not store a token.                             |
| Route guards                       | Implemented | `beforeLoad` on `/` redirects when `getDevAuth()` is valid. `beforeLoad` on `/demo` redirects to `/` when it is missing or expired.                                |
| Session start has no identity mint | Implemented | `StartScreen` is CTA-only. `LiveSessionScreen` does not call `mintDevToken` or render `InvestorPicker`. `InvestorPicker` no longer remints.                        |
| Auth errors and password privacy   | Implemented | `UNAUTHENTICATED` and `VALIDATION_ERROR` map to `auth.*` i18n keys. Password stays in React state and is not written to `setDevAuth`.                              |

### Coherence (Design)

| Decision                                                          | Followed? | Notes                                                                        |
| ----------------------------------------------------------------- | --------- | ---------------------------------------------------------------------------- |
| Overlay on `/`, skip reduced motion, valid token never paints `/` | Yes       | Overlay lives on `LoginScreen`. Authenticated `/` redirects in `beforeLoad`. |
| `beforeLoad` + `redirect` guards                                  | Yes       | Unauthenticated `/demo` to `/`. Authenticated `/` to `/demo`.                |
| Login is the only mint site                                       | Yes       | Start and InvestorPicker do not mint.                                        |
| Digit ClientId: `inputMode="numeric"`, trim, `/^\d+$/`            | Yes       | `type="text"` with numeric inputMode.                                        |
| Native WebView URI stays `/demo`                                  | Yes       | Guard tests cover `/demo`. `apps/native` unchanged.                          |
| `mintDevToken(clientId, password)` and required schema `password` | Yes       | Contracts and advisor-service match.                                         |
| Error map and password in React state                             | Yes       | Matches design interfaces.                                                   |
| `createAppRouter` for memory-history tests                        | Yes       | Compatible extra. Design listed `router.tsx` modify.                         |

### Issues Found

**CRITICAL**: None
**WARNING**: None
**SUGGESTION**: `maps VALIDATION_ERROR to auth copy` asserts mapped copy and does not assert `navigate` was skipped. Stay-on-login is still observed because the alert renders on `LoginScreen`. Vite reports LiveSessionScreen >500 kB after minify. Live mint was not proven in the browser because the agent was down.

### Verdict

PASS
18/18 tasks complete. 14/14 scenarios have passing covering tests. `npm run test -w apps/web` and `npm run build` exited 0.
