# @loopops/contracts

Shared API contract v0 for the Actinver AI advisor POC.

TypeScript types and Zod schemas are the source of truth for the web client.
The backend team mirrors these in Pydantic at
`apps/agent/src/actinver_agent/schemas/contract.py` when they scaffold the API.

## SSE events

| Event       | Payload                                                                |
| ----------- | ---------------------------------------------------------------------- |
| `token`     | `{ "text": string }` — streamed narrative (chat mode)                  |
| `ui`        | `UIComponent` — server-driven card                                     |
| `citations` | `{ "items": Citation[] }`                                              |
| `error`     | `{ "code": string, "message": string }`                                |
| `done`      | `{ "turn_id": string, "evidence_id": string, "service_type": string }` |

## UI component types

- `portfolio_summary`
- `attribution_bars`
- `citations`
- `warning_banner`

Unknown types render nothing on the client and log a telemetry event.
