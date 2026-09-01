# Tino POC — project docs

Distilled context for the LoopOps Avatar App POC. Source material: Actinver client briefs (September 2026) and the three-screen storyboard.

**Not stored here:** the original client document set. This folder holds only what the build team needs.

## Index

| Doc                                                        | Audience | Contents                                         |
| ---------------------------------------------------------- | -------- | ------------------------------------------------ |
| [product-context.md](./product-context.md)                 | Everyone | What Tino is, POC scope, razonabilidad guardrail |
| [storyboard-and-journeys.md](./storyboard-and-journeys.md) | FE + BE  | Three screens, demo journeys, copy rules         |
| [mock-data-guide.md](./mock-data-guide.md)                 | FE       | Mock schemas, fixtures, conversation scenarios   |

## Code references

| Path                  | Purpose                              |
| --------------------- | ------------------------------------ |
| `apps/web/src/mocks/` | Zod schemas + Rodrigo fixture data   |
| `packages/contracts/` | API contract v0 (SSE + `ui_payload`) |
| `apps/agent/`         | Backend handoff (not FE-owned)       |

## Reading order

1. **product-context.md** — why we build this and what is out of scope
2. **storyboard-and-journeys.md** — what the UI should feel like
3. **mock-data-guide.md** — how to wire mocks into chat and Explorar
