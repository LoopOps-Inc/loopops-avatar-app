# Agent instructions — apps/agent

You own the Python backend for the Actinver AI advisor POC.

## Read first

1. [`README.md`](./README.md) — implementation handoff (endpoints, graph, done criteria)
2. [`../../knowledge/poc-scope.md`](../../knowledge/poc-scope.md) — POC vs production scope
3. [`../../packages/contracts/README.md`](../../packages/contracts/README.md) — API shapes the web client expects

BA reference (sibling repo `actinver-ai-advisor`):

- `docs/04-backend/04-api-contract.md`
- `docs/04-backend/01-backend-architecture.md`
- `docs/01-architecture/06-agent-architecture.md`

## Rules

- **Python 3.12**, **FastAPI**, **LangGraph**, **LangChain**, **Gemini** (optional).
- Pydantic models in `schemas/contract.py` must mirror `packages/contracts` (TypeScript/Zod).
- **Split-channel rendering:** `speech` is qualitative; exact figures go in `ui_payload` only.
- **Read-only tools** for POC. No order placement, no mutations.
- `client_id` is injected from session context, never parsed from model output.
- `GOOGLE_API_KEY` stays server-side only. Never add vendor keys under `apps/web/`.
- CORS: allow `http://localhost:8080`.

## Do not build yet (out of POC)

- Microservice split (`avatar-broker`, `voice-pipeline`, etc.)
- Suitability engine, transactions, step-up auth
- WORM audit, guardrail service, egress proxy
- Real core banking APIs (use mocks)

## Suggested first PR

1. `pyproject.toml` + uv setup
2. FastAPI app with `/healthz`, `/v1/sessions`, `/v1/threads/{id}/messages` (SSE)
3. LangGraph graph with two intents and mock tools
4. Composer with split-channel enforcement
5. One pytest asserting figures stay out of `speech`

## Verify before opening PR

```sh
cd apps/agent
uv run pytest
uv run uvicorn actinver_agent.main:app --port 8000
# curl session + SSE message (see README)
```

When the API is ready, notify the frontend team so they can wire `/advisor` in `apps/web`.
