## Exploration: add-login-and-splash

### Current State

The web app is a Vite + React + TanStack Router client. `apps/web/src/router.tsx` defines only `/demo`. There is no `/` index, no `/login`, and no `beforeLoad` or redirect. `main.tsx` mounts `RouterProvider` with that tree. Visiting `/` (browser or native WebView at `http://localhost:8080`) does not enter the live session.

`/demo` is `LiveSessionRoute`. It shows `StartScreen` until the user starts a session, then swaps to `SessionPanel`. Identity today is a demo investor picker:

- `useInvestors` loads `GET /v1/config/investors` and stores `numero_cliente_unico` in `sessionStorage` (`loopops.selectedInvestor`).
- `StartScreen` renders `InvestorSelect`. On Start, `handleStart` calls `mintDevToken(String(selected.numero_cliente_unico))`, then `setDevAuth`, then advisor/avatar session setup.
- `InvestorPicker` is unused in production (tests only). It also calls `mintDevToken(clientId)` with no password.

`mintDevToken` in `apps/web/src/services/advisor-service.ts` POSTs `{ client_id }` only. `advisor-service.test.ts` asserts that body. The backend on this branch already requires both fields:

- `POST /v1/auth/dev-token` (`services/agent/src/actinver_agent/api/routes/auth.py`) compares `body.password` to `AUTH_DEV_PASSWORD` (`SecretStr("actinver123")`) with `hmac.compare_digest`.
- Wrong password → 401 `UNAUTHENTICATED`. Missing `client_id` or `password` → 422 `VALIDATION_ERROR` (`extra="forbid"` on `DevTokenRequest`).
- `packages/contracts` `DevTokenRequestSchema` still has `client_id` only. No `password`.

`dev-auth.ts` keeps `{ clientId, accessToken, expiresAt }` in `sessionStorage` (`actinver.dev-auth`). `authHeaders()` attaches `Bearer` when present. Session, consent, and avatar routes use `require_client`. Investor list and `GET /v1/config` do not. JWT `sub` is the string `client_id`. Backend `resolve_id_cliente` accepts `numero_cliente_unico` digits (`200001`–`200020`), small pk `1`–`20`, or aliases such as `cl_demo_moderado`.

Vite `/api` proxy injects a bearer token when the request has no `Authorization`. Local `/demo` can still reach protected APIs without the login UI. Docker/production does not get that free token unless the client stores one.

Native (`apps/native`) is a WebView of the web app. No native login or splash. Login on `/` in web is enough for the WebView.

i18n has `live.*` and `advisor.*` only. No `auth` or `splash` keys. Design tokens: splash/login must use `bg-filled-dark`, `text-advisor-submit-fg` / gold, `bg-surface`, `text-error`. Primary CTA is filled-dark, not blue. Brand assets already exist: `/tino-icon.png`, `TinoMark`.

Start without a password is already broken against this backend. Login must mint the token. Start must stop minting.

### Affected Areas

- `apps/web/src/router.tsx` — add `/` (login + splash), guard `/demo`, authenticated redirect from `/`
- `apps/web/src/features/auth/` (new) — `LoginScreen`, splash overlay, submit hook
- `apps/web/src/services/advisor-service.ts` — `mintDevToken(clientId, password)` body `{ client_id, password }`
- `apps/web/src/services/advisor-service.test.ts` — expect password in body; 401/422 mapping
- `apps/web/src/services/dev-auth.ts` — reuse as-is (token store; do not persist password)
- `packages/contracts/src/index.ts` — add `password` to `DevTokenRequestSchema`
- `apps/web/src/features/avatar/components/LiveSessionScreen.tsx` — stop minting on Start; drop investor props if picker is removed
- `apps/web/src/features/avatar/components/StartScreen.tsx` — keep session CTA; remove `InvestorSelect`
- `apps/web/src/features/avatar/components/LiveSessionScreen.test.tsx` — no picker mint; assume stored auth
- `apps/web/src/features/avatar/components/InvestorPicker.tsx` (+ test) — unused; signature change will break tests unless updated or left out of this change
- `apps/web/src/i18n/translations/es.json` + `en.json` — login, splash, validation, error copy
- `apps/web/src/components/AppShell.tsx` — reuse for login layout
- `apps/native/App.tsx` / `WebViewContainer.tsx` — no native UI; confirm WebView still loads `/`
- `services/agent` auth routes — already done; do not reopen unless a contract mismatch appears
- `knowledge/architecture.md` — still says `/` redirects to `/demo`; update in a later docs pass, not this explore file

### Approaches

#### Splash presentation

1. **Timed branded overlay on the login route** — `/` paints navy/gold splash (`bg-filled-dark`, gold mark/title), then reveals the login form after a short timer. No extra URL.
   - Pros: Matches a branded first paint. Native WebView at `/` sees it. One route. Easy to skip when a valid token already exists.
   - Cons: Timer is arbitrary. Must honor `prefers-reduced-motion` (skip or shorten).
   - Effort: Low

2. **Distinct `/splash` route** — splash then `navigate` to `/` or `/demo`.
   - Pros: Isolated screen. Easy to deep-link past it.
   - Cons: Extra history entry. Native must load `/splash` or `/` must redirect. More router work for little gain.
   - Effort: Medium

3. **Login page as first paint (no splash timer)** — form is the first thing users see, maybe with the same navy header.
   - Pros: Fastest path to credentials. No motion issues.
   - Cons: Misses the requested splash.
   - Effort: Low

#### Login path and `/demo` guard

1. **Login at `/`; `/demo` `beforeLoad` requires `getDevAuth()`** — unauthenticated `/demo` → `/`. Authenticated `/` → `/demo`. Success `navigate({ to: '/demo' })`.
   - Pros: Native already loads `/`. Matches "login then `/demo`". Guard lives in the router, not inside the session screen. TanStack Router `beforeLoad` + `redirect` is the standard pattern (none exists today).
   - Cons: Client-only guard. Vite proxy can still call APIs without the UI login in local dev.
   - Effort: Medium

2. **Login at `/login`; `/` redirects to `/login` or `/demo`**
   - Pros: `/login` is explicit.
   - Cons: Extra hop. Native loads `/`, so `/` still needs a redirect. More routes for the same UX.
   - Effort: Medium

3. **Keep login as a state of `/demo` (no new route)**
   - Pros: Smallest router diff.
   - Cons: Conflicts with "navigate to `/demo`" after success. Mixes auth with session start. Harder to guard deep links.
   - Effort: Low (wrong shape)

#### InvestorSelect on StartScreen

1. **Replace: login is identity; remove picker from StartScreen** — Start only starts the live session using the stored token. Do not call `mintDevToken` again.
   - Pros: Password is entered once. Matches numeric ClientId. Avoids a second mint that would 422 without a stored password. StartScreen stays as the "Habla con Tino" CTA.
   - Cons: Switching investor requires logout + login (acceptable for this demo password).
   - Effort: Low

2. **Keep picker and re-mint on Start** — would need the password in memory or storage.
   - Pros: Fast investor switch for demos.
   - Cons: Storing password is unsafe. Prompting again duplicates login. Current `mintDevToken` callers have no password and will 422.
   - Effort: Medium (and fights the new login)

3. **Defer picker to a later change** — hide it now, keep files.
   - Pros: Smaller product scope. `InvestorSelect` / `useInvestors` stay for a follow-up.
   - Cons: Dead UI code until cleaned up. `InvestorPicker` tests still assume `mintDevToken(id)`.
   - Effort: Low (same as replace if StartScreen drops the picker)

#### ClientId numeric UI vs `client_id: str`

1. **Digit input, send string** — `inputMode="numeric"`, `pattern="[0-9]*"`, no `type="number"`. Validate digits client-side. POST `client_id: trimmedString`.
   - Pros: Matches the request (numeric ClientId). Avoids number-input spinners and empty-value bugs. Backend already documents "Client ID or numero_cliente_unico" and resolves `"200001"`.
   - Cons: Demo aliases (`cl_demo_moderado`) cannot be typed. That is intended if the field is numeric.
   - Effort: Low

2. **Free-text ClientId** — allows aliases and digits.
   - Pros: Matches JWT `sub` and backend aliases.
   - Cons: Conflicts with "ClientId (numeric)".
   - Effort: Low

#### Error, loading, empty fields

1. **Client validate, then map `ApiError.code`** — disable submit until both fields have values (ClientId digits, password non-empty). Submitting shows a spinner on the filled-dark CTA (`Loader2`, same as Start). Map `UNAUTHENTICATED` → generic invalid-credentials copy. `VALIDATION_ERROR` → check-the-fields copy. Other/network → existing unknown-error pattern. `role="alert"` + `text-error` / `bg-error/10`. Do not show raw backend `message` or the submitted password.
   - Pros: Matches current `throwProblem` / `ApiError` and StartScreen alert styling. i18n-only copy.
   - Cons: Backend 422 vs empty-field UX must stay distinct (client should not send empty bodies).
   - Effort: Low

2. **HTML `required` only** — browser bubbles, no i18n.
   - Pros: Tiny.
   - Cons: Breaks i18n and writing-style rules.
   - Effort: Low (reject)

#### Web vs native

1. **Web-only (`apps/web` + contracts); native inherits via WebView**
   - Pros: Native already loads `http://localhost:8080`. No RN login. NOM-151 bridge unchanged.
   - Cons: If a host later opens `/demo` directly, the web guard must redirect to `/`.
   - Effort: Low extra

2. **Native splash/login in React Native**
   - Pros: Native-looking chrome.
   - Cons: Duplicate UI, tokens, and i18n. Out of scope.
   - Effort: High

### Recommendation

Build this as a **web-only auth gate** in `apps/web`.

- **Splash:** timed branded overlay on `/` (approach 1). Navy `bg-filled-dark`, gold mark/title from existing tokens and `/tino-icon.png` or `TinoMark`. About 1.5s, skip when `prefers-reduced-motion` or when `getDevAuth()` is already valid. Do not add `/splash`.
- **Login:** `/` is the login route (ClientId digits + password + filled-dark submit). Success stores token via `setDevAuth` and **navigates to `/demo`**. Authenticated visits to `/` redirect to `/demo`. Unauthenticated `/demo` `beforeLoad` redirects to `/`. Do not use `/login`.
- **StartScreen:** keep the post-login "Habla con Tino" CTA. **Remove InvestorSelect** from Start. **Stop calling `mintDevToken` in `handleStart`**. Login is the identity switcher. Leave `InvestorSelect` / `useInvestors` in the tree unused, or drop their wiring only; do not keep a second mint. Update or skip `InvestorPicker` tests when the `mintDevToken` signature changes. Do not persist password.
- **ClientId:** numeric input, send `String` to `{ client_id, password }`. Do not use `type="number"`.
- **Errors:** client-side empty-field blocking + `ApiError.code` mapping to i18n. Keys in both `es.json` and `en.json`. Network calls stay in `advisor-service.ts`.
- **Contracts:** add `password: z.string()` to `DevTokenRequestSchema`. Do not change `services/agent` in this change.
- **Native:** no `apps/native` UI. Confirm WebView still opens `/`.

Backend work in `c4e620af` is the source of truth. Frontend and contracts are the gap.

### Risks

- **Start and InvestorPicker still mint without password.** Until `mintDevToken` and Start change, `/demo` Start returns 422 against this backend.
- **Vite proxy injects a bearer token** when `Authorization` is missing. Local unauthenticated `/demo` can still call session APIs. The UI guard is not a server lock. Do not treat proxy injection as product auth.
- **`DevTokenRequestSchema` lacks `password`.** If the web client starts sending it before contracts update, types and any schema parse of the request will drift.
- **Numeric ClientId cannot type `cl_demo_moderado`.** Backend tests use that alias. Demo users must type `200001` (or another `numero_cliente_unico`). Document that in the spec.
- **sessionStorage auth** clears when the tab closes. That is acceptable for a shared demo password. Do not use `localStorage` for the token without a later decision.
- **Client-only `/demo` guard.** Deep links work in the SPA. A stale token (`expiresAt`) is already cleared by `getDevAuth()`.
- **i18n and writing-style.** New copy must be short, no emojis, no em dashes, both locales.
- **Review budget.** Router + login/splash + service + i18n + StartScreen + tests can approach the 400-line authored budget. `sdd-tasks` should forecast chained PRs if the slice grows (UI first vs service/contracts first).
- **architecture.md is stale** (`/` → `/demo`). Fix in docs when this change lands, not as a blocker.

### Ready for Proposal

Yes. Scope, routes, splash shape, identity replacement, ClientId mapping, and error behavior are clear. Backend is already on the branch. Orchestrator should tell the user: login lives at `/` with a short navy/gold splash, success goes to a guarded `/demo`, InvestorSelect comes off StartScreen, and `mintDevToken` must send `password`. Next phase: `sdd-propose`.
