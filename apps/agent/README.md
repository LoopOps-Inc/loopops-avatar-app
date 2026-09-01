# Agent backend — implementation handoff

**Owner:** Backend developer  
**Status:** Not started — scaffold from this document  
**Stack:** Python 3.12 · FastAPI · LangGraph · LangChain · Gemini

The web app (`apps/web`) will call this service once it is running. Until then,
`/demo` works standalone via the HeyGen sandbox.

---

## Before you start

1. Read [`knowledge/poc-scope.md`](../../knowledge/poc-scope.md) for POC boundaries.
2. Read the BA reference docs in sibling repo `actinver-ai-advisor`:
   - `docs/04-backend/04-api-contract.md`
   - `docs/04-backend/03-tool-catalog.md`
   - `docs/01-architecture/06-agent-architecture.md`
3. Mirror request/response shapes from [`packages/contracts`](../../packages/contracts).
   TypeScript + Zod there is the source of truth for the web client.

---

## POC deliverable

One FastAPI process (`bff-mobile` role) that exposes:

| Method | Path                               | Response                                                             |
| ------ | ---------------------------------- | -------------------------------------------------------------------- |
| `POST` | `/v1/sessions`                     | JSON — `thread_id`, `capabilities`, `disclosures_required`, `client` |
| `POST` | `/v1/threads/{thread_id}/messages` | SSE stream                                                           |
| `GET`  | `/healthz`                         | `{ "status": "ok" }`                                                 |

CORS must allow `http://localhost:8080` (Vite dev server).

### SSE events (chat turn)

Every turn ends with `done`, including after `error`.

| Event       | Payload                                                        |
| ----------- | -------------------------------------------------------------- |
| `token`     | `{ "text": "..." }` — streamed narrative (append on client)    |
| `ui`        | `UIComponent` — see `packages/contracts`                       |
| `citations` | `{ "items": Citation[] }`                                      |
| `error`     | `{ "code": "...", "message": "..." }`                          |
| `done`      | `{ "turn_id", "evidence_id", "service_type": "no_asesorado" }` |

---

## Suggested package layout

```
apps/agent/
├── pyproject.toml
├── .env.example
├── README.md
├── AGENTS.md              ← agent instructions
├── src/actinver_agent/
│   ├── main.py            # FastAPI app, CORS, router mount
│   ├── config.py          # pydantic-settings (GOOGLE_API_KEY, CORS, etc.)
│   ├── api/
│   │   ├── routes.py      # /v1/sessions, /v1/threads/{id}/messages
│   │   └── sessions.py    # in-memory thread store (POC)
│   ├── schemas/
│   │   └── contract.py    # Pydantic models mirroring packages/contracts
│   ├── agent/
│   │   ├── graph.py       # LangGraph: route → tools → compose → optional LLM
│   │   ├── composer.py    # split-channel: speech vs ui_payload
│   │   └── tools.py       # read-only mock tools (portfolio, market)
│   └── mocks/
│       └── data.py        # static portfolio / news fixtures
└── tests/
    └── test_composer.py   # assert no exact figures in speech
```

Use [uv](https://docs.astral.sh/uv/) for dependency management.

Suggested dependencies: `fastapi`, `uvicorn`, `pydantic-settings`, `sse-starlette`,
`langgraph`, `langchain-core`, `langchain-google-genai`.

---

## LangGraph shape (POC)

```
START → route_intent → execute_tools → compose_response → enhance_speech (optional) → END
```

| Node               | Responsibility                                                                |
| ------------------ | ----------------------------------------------------------------------------- |
| `route_intent`     | Classify `portfolio_inspect` or `market_context` (keywords or small LLM call) |
| `execute_tools`    | Call mock tools; build provenance map for every numeric value                 |
| `compose_response` | Produce `AgentTurnOutput`: `speech` + `ui_payload[]`                          |
| `enhance_speech`   | Optional Gemini pass to polish narrative only (skip if no API key)            |

**Invariants (non-negotiable for POC):**

- `client_id` comes from the session/token, never from model output.
- Exact figures live in `ui_payload` only. `speech` is qualitative.
- All tools are read-only. No mutations.
- Numbers in `ui` must trace to a tool result in the same turn.

---

## Mock tools (v0)

| Tool                        | POC data                             |
| --------------------------- | ------------------------------------ |
| `get_portfolio_performance` | Market value ~$4.18M MXN, MTD +0.87% |
| `get_portfolio_attribution` | Deuda gub. +118 bp, RV local −52 bp  |
| `search_market_news`        | 2 items (Banxico, peso)              |
| `get_market_quote`          | USDMXN ~18.42                        |

See `actinver-ai-advisor/docs/04-backend/03-tool-catalog.md` for full catalogue.

---

## Split-channel example

Client asks: _"¿Cómo va mi portafolio?"_

```json
{
  "speech": "Tu portafolio cerró el mes ligeramente al alza. Casi todo el movimiento vino de deuda gubernamental. Te dejo el desglose en pantalla.",
  "ui_payload": [
    {
      "type": "portfolio_summary",
      "payload": {
        "as_of": "2026-08-31",
        "market_value": { "amount": "4187203.55", "currency": "MXN" },
        "period_return_pct": 0.87,
        "period": "MTD"
      }
    },
    {
      "type": "attribution_bars",
      "payload": {
        "contributions": [
          { "sleeve": "Deuda gubernamental", "bps": 118 },
          { "sleeve": "Renta variable local", "bps": -52 }
        ]
      }
    }
  ]
}
```

`4187203.55` must not appear in `speech`.

---

## Environment variables

```env
GOOGLE_API_KEY=          # optional — Gemini speech polish
AGENT_USE_LLM=true
CORS_ORIGINS=http://localhost:8080
```

---

## Run locally

```sh
cd apps/agent
uv sync
uv run uvicorn actinver_agent.main:app --reload --port 8000
```

Verify:

```sh
curl -s -X POST http://localhost:8000/v1/sessions | jq .
curl -N -X POST http://localhost:8000/v1/threads/<thread_id>/messages \
  -H 'Content-Type: application/json' \
  -d '{"message":"¿Cómo va mi portafolio?"}'
```

---

## Web integration (after API is ready)

The frontend team will:

1. Proxy `/api` → `http://localhost:8000` in `apps/web/vite.config.ts`
2. Add `apps/web/src/services/advisor-service.ts` (SSE client)
3. Wire SSE into the `/demo` chat transcript

Contract types: `import { ... } from '@loopops/contracts'`.

---

## Out of scope for first PR

- `avatar-broker`, voice pipeline, LiveAvatar LITE
- Suitability engine, transactions, Form Spec
- Guardrail service, audit/WORM evidence
- Real Actinver core API integration
- Auth (DPoP, device binding) — use mock session for POC

---

## Definition of done

- [ ] `POST /v1/sessions` returns valid JSON per `SessionResponseSchema`
- [ ] `POST /v1/threads/{id}/messages` streams SSE with `token`, `ui`, `done`
- [ ] Portfolio and market intents return split-channel responses
- [ ] Test: no exact monetary amounts in `speech`
- [ ] `GET /healthz` returns 200
- [ ] README documents how to run and test
