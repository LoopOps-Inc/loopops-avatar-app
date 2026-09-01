# Deployment

Kubernetes is the only substrate (ADR-0011). One image (`Dockerfile`), five
Deployments (`ops/k8s/base`), one namespace per environment, GitOps
reconciliation. Migrations run forward-only as an init job.

## Environments and posture

`Settings.validate_posture()` refuses local-only bindings outside `ENVIRONMENT=local`.

| Setting | local | dev | staging | prod |
|---|---|---|---|---|
| `LLM_PROVIDER` | `stub` (or `gemini_api` with an AI Studio key) | `vertex` | `vertex` | `vertex` |
| `VERTEX_PROJECT_ID` / `VERTEX_LOCATION` | dev project | dev project | staging project, region-pinned | prod project, Mexico region where available (ADR-0018) |
| `CORE_PROVIDER` | `synthetic` | `synthetic` | `http` against staging cores (generated data) | `http` |
| `AUTH_MODE` | `dev` | `oidc` | `oidc` | `oidc` |
| `AUTH_DPOP_REQUIRED` | `false` | `true` | `true` | `true` |
| `LIVEAVATAR_PROVIDER` / `IS_SANDBOX` | `stub` / `true` | `real` / `true` | `real` / `true` (+ canary) | `real` / `false` |
| `VOICE_PROVIDER` | `stub` | `google` | `google` | `google` |
| `OBJECT_STORE_LOCK_MODE` | `GOVERNANCE` | `GOVERNANCE` | `GOVERNANCE` | `COMPLIANCE` (enforced) |
| `CACHE_PROVIDER` / `CHECKPOINTER_PROVIDER` | redis / postgres (memory in unit tests) | redis / postgres | redis / postgres | redis / postgres |
| `SVC_*_URL` | container names | cluster services | cluster services | cluster services |
| Data | synthetic | synthetic | generated, production-shaped, never real | real |

Real client data never leaves production; staging uses generated data.

## Secrets

The environment carries references only. In Kubernetes the External Secrets
Operator materialises them (`ops/k8s/base/externalsecrets.yaml`) into mounted
files referenced as `file://<name>` or into Secrets Manager entries referenced as
`secretsmanager://…` / `kms://…`. Startup fails if a reference field looks like
a secret value.

Key placement (docs/05-security/04 §2):

| Key | Reference | Mounted into |
|---|---|---|
| Form Spec HMAC (agent-readable) | `kms://actinver/formspec-hmac` | agent, transaction |
| Suitability HMAC (**not** agent-readable) | `kms://actinver/suitability-hmac` | suitability only. The agent asserts at startup that it cannot resolve it. |
| LiveAvatar API key | `secretsmanager://actinver/liveavatar/api-key` | agent (broker) |
| Client hash salt | `secretsmanager://actinver/client-hash-salt` | all |
| Dev signing key | `secretsmanager://actinver/dev-signing-key` | local/dev only |

Rotation per docs/05-security/04 §3; the suitability key retires with a
five-year overlap so old verdicts stay verifiable.

## Rollout

1. `docker build` → SBOM → scan → sign (CI, `.github/workflows/agent-ci.yml`).
2. Deploy to dev on merge; staging on tag with the integration suite, adversarial
   corpora and the evaluation suites; production on tag + approval.
3. Canary 5 % for 48 h, then the ADR-0015 ladder (internal staff → 1 % → 10 % →
   25 % → 50 % → 100 %) gated on P1 = 0, guardrail block rate in band,
   escalation rate flat and Compliance sign-off.
4. Rollback: previous image for code; **flags** for prompt (`advisor.prompt.version`),
   model (`advisor.model.primary`) and rules (`advisor.suitability.ruleset_version`)
   without a deploy.

## Kill switch and incident hooks (RB-07, 05-security/06)

- `PUT /v1/compliance/flags/advisor.kill_switch {"value":"on"}` by Risk or the
  incident commander (roles `risk`/`sre`). New turns return the legally approved
  static message, avatar sessions are torn down, `/v1/config` shows the switch
  within the 30-second poll.
- Capability flags: `advisor.intent.advisory_recommend`, `advisor.intent.transactional`,
  `advisor.voice_mode`, `advisor.avatar` (Compliance/Product owners).
- Cohort revocation: `POST /v1/compliance/sessions/revoke`.
- Thread freeze + legal hold: `POST /v1/compliance/threads/{id}/freeze`.
- Evidence store outage: advisory/transactional turns refuse; informational turns
  spool; drain with `cli drain-spool`, verify with `cli verify-chain --thread`.

## Kubernetes specifics (`ops/k8s/base`)

- Probes: `/healthz` liveness, `/readyz` readiness (fails when suitability,
  guardrail or audit are unreachable → pod receives no traffic).
- `agent` Deployment: `terminationGracePeriodSeconds: 900` so live avatar
  WebSockets drain; session affinity on `avatar_session_id` at the gateway
  (`httproute.yaml`); HPA on the custom metric `concurrent_turns`.
- PodDisruptionBudget `minAvailable: 60%`.
- Security context: non-root, read-only root filesystem, all capabilities
  dropped, seccomp `RuntimeDefault`.
- NetworkPolicies mirror docs/01-architecture/02 §4 (default deny; agent → controls
  on 8443; data zone ingress only; egress through the proxy).
- Migrations: init container running `python -m actinver_agent.cli migrate`.
- Checkpoint partitioning and retention: `ops/sql/checkpoint_partitioning.sql`,
  `ops/sql/retention.sql`, `cli retention` as a CronJob (180-day operational data).
- Daily anchor job: `cli anchor` (CronJob) publishes chain heads to the anchor
  bucket in a separate trust domain.

```sh
kubectl apply -k ops/k8s/overlays/dev
```

## Vendors

- **Vertex AI**: workload identity federation, region pinning, no-training terms,
  Private Service Connect (ADR-0003). `GOOGLE_APPLICATION_CREDENTIALS` is only
  for local experiments.
- **LiveAvatar**: sandbox for dev/staging (`LIVEAVATAR_IS_SANDBOX=true`, Wayne
  avatar), production avatar id and voice from `AVATAR-ACTINVER.md`; API key
  rotated quarterly with a 7-day overlap.
- **Object store**: any S3-compatible store with Object Lock; buckets created
  with `ObjectLockEnabledForBucket` (see `ops/floci/init.sh` for the exact calls).
