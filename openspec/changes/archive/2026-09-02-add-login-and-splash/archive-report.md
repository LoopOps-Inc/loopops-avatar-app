# Archive Report: add-login-and-splash

**Change**: add-login-and-splash
**Closed**: 2026-09-02
**Archived to**: `openspec/changes/archive/2026-09-02-add-login-and-splash/`
**Store**: openspec (filesystem locators were authoritative)
**Verdict at close**: PASS

## Final State

The cycle is closed. `tasks.md` shows 18/18 implementation tasks checked. Verify verdict is PASS: 6/6 requirements, 14/14 scenarios, 0 CRITICAL findings, 0 WARNING findings. `npm run test -w apps/web` passed 79/79 tests. `npm run build` exited 0.

Maintainer accepted `size:exception`. Apply ran tasks 1.1–4.5 in one batch on `feature/login`. Apply counted 1430 lines including OpenSpec artifacts. Unrelated ChatArea/ChatLoading diffs from apply were reverted before verify.

Browser check is informational (no web e2e in this change). Splash then login was observed at `/`. Unauthenticated `/demo` redirected to `/`. Live mint was not proven in the browser because the agent backend was down.

## Task Completion Gate

Passed. Persisted `tasks.md` has 0 unchecked implementation tasks (`- [ ]` count 0; 18 `[x]` lines). No archive-time checkbox reconciliation was required.

## Specs Synced

| Domain   | Action  | Details                                                                                                                            |
| -------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| web-auth | Created | New full spec promoted to `openspec/specs/web-auth/spec.md`. 6 requirements added. 0 modified. 0 removed. Not a destructive merge. |

`openspec/specs/web-auth/spec.md` did not exist. The change spec is a full spec (Purpose + Requirements), not an ADDED/MODIFIED/REMOVED delta. It was copied with `cp` then `mv` through a temp file. `diff -r` of source vs temp and source vs main spec produced empty output (byte-identical).

Archive config rule "Warn before merging destructive deltas": not applicable. No existing main-spec requirements were replaced or deleted.

Archive config note: `knowledge/architecture.md` still describes `apps/agent` as planned; the live backend is `services/agent`. This change left `services/agent` unchanged.

## Mechanical Readback

Verbatim `diff -r` stdout was empty in every comparison. Empty output is the passing evidence.

### Spec copy (source vs temp, then source vs main)

```text
(empty)
```

### Archive move fallback (snapshot vs remaining source after `git mv` status 128)

`git mv` failed with status 128 (`fatal: source directory is empty`) because the change folder was untracked. Source remained on disk and matched the pre-move snapshot. Plain `mv` then ran.

```text
(empty)
```

### Archive move (pre-move snapshot vs destination)

```text
(empty)
```

## Archive Contents

- proposal.md
- specs/web-auth/spec.md
- design.md
- tasks.md (18/18 complete)
- verify-report.md
- apply-progress.md
- exploration.md
- preproposal.yaml
- state.yaml
- .gentle-ai-instance

Active path `openspec/changes/add-login-and-splash/` is absent.

## Artifacts Read (traceability)

Authoritative reads were OpenSpec files (store: openspec). Engram observations below were located by search for the same change. Full artifact text used for this report came from the filesystem locators, not Engram previews.

| Artifact                   | Filesystem locator (read)                                      | Engram observation                    |
| -------------------------- | -------------------------------------------------------------- | ------------------------------------- |
| proposal                   | `openspec/changes/add-login-and-splash/proposal.md`            | id 15, sync_id `obs-92c52abad1db7b1f` |
| spec                       | `openspec/changes/add-login-and-splash/specs/web-auth/spec.md` | id 16, sync_id `obs-1cd3ce1ffffcea07` |
| design                     | `openspec/changes/add-login-and-splash/design.md`              | id 17, sync_id `obs-4f2843822a465a03` |
| tasks                      | `openspec/changes/add-login-and-splash/tasks.md`               | id 18, sync_id `obs-4d7961bbad40e54f` |
| apply-progress             | `openspec/changes/add-login-and-splash/apply-progress.md`      | id 20, sync_id `obs-682830b193ae4706` |
| verify-report              | `openspec/changes/add-login-and-splash/verify-report.md`       | id 21, sync_id `obs-333e8e9ddfce63f9` |
| exploration (not required) | `openspec/changes/add-login-and-splash/exploration.md`         | id 13, sync_id `obs-e157174890ac6999` |

Related Engram observation id 19, sync_id `obs-d32d24c9b95e1ca4` (`SDD login splash planned`) described apply blocked on chain-strategy at planning time. That is not the state at close: maintainer accepted `size:exception` and apply completed 18/18.

## Snapshot vs Close (Final-State Authority)

`apply-progress` and `verify-report` agree with close on completion and PASS. Design.md still contains an open-question checkbox that specs were missing at design time. Specs later landed; that checkbox is historical, not an open gap at archive.

Proposal success-criteria checkboxes remain unchecked in the proposal artifact. Those are proposal criteria, not implementation tasks. Implementation completion is recorded in `tasks.md`.

## Source of Truth

`openspec/specs/web-auth/spec.md` now holds splash overlay, login mint, successful auth, route guards, session-start identity, and auth-error/password-privacy requirements.

## SDD Cycle Complete

The change has been planned, implemented, verified, and archived. Ready for the next change.
