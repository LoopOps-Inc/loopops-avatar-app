# Mock data guide (FE)

Frontend-owned mock layer until `apps/agent` serves live data.

## Location

```
apps/web/src/mocks/
├── schemas/          # Zod domain schemas
├── fixtures/
│   └── rodrigo.ts    # Primary POC persona dataset
├── scenarios.ts      # Intent → response mapping for chat mock
└── index.ts          # Public exports
```

## Schemas

| Schema                           | Entity                     | Used for                             |
| -------------------------------- | -------------------------- | ------------------------------------ |
| `MoneySchema`                    | `{ amount, currency }`     | All monetary values (string amounts) |
| `UserSchema`                     | Client identity            | Header initials, session, forms      |
| `AdvisorSchema`                  | Assigned human advisor     | Handoff, opening copy                |
| `InvestorProfileSchema`          | _Perfil del inversionista_ | Razonabilidad, chips                 |
| `AccountSchema`                  | _Cuenta_ / cash            | Idle cash journey                    |
| `PositionSchema`                 | Single holding             | Explorar list, attribution           |
| `PortfolioSchema`                | Summary + positions        | Home card, F2 answers                |
| `ProductSchema`                  | Instrument catalogue       | F3 cards                             |
| `ProductProfileSchema`           | Committee risk profile     | Eligibility, blocks                  |
| `AttributionSchema`              | Why portfolio moved        | Journey B                            |
| `SuggestionChipSchema`           | Next-step chips            | Chat UI                              |
| `SuitabilityJustificationSchema` | FR-0.2 card                | Passed suggestion                    |
| `BlockedProductSchema`           | FR-0.3 card                | Failed razonabilidad                 |
| `HandoffBriefingSchema`          | F5 advisor packet          | Schedule flow                        |
| `FormDraftSchema`                | Screen 3 modal             | Signature demo                       |

API transport shapes (`ui_payload`, SSE) stay in `packages/contracts`. Domain mocks feed the mock service and future UI screens (Explorar, modal).

## Primary fixture — `rodrigo`

Import:

```ts
import { rodrigoFixture, getExplorarSummary, getPortfolioAttribution } from '@/mocks';
```

Includes:

- `user` — Rodrigo Beltrán, initials DR
- `advisor` — Fernanda Ruvalcaba
- `investorProfile` — moderado, horizon, objectives
- `explorarSummary` — storyboard home card ($948,250, −2.4%)
- `fullPortfolio` — persona-level totals (MXN 14.5M)
- `accounts` — cuenta with MXN 3,041,200 idle
- `positions` — CETES 28d, ACTIREN, NAFTRAC
- `products` — eligible and ineligible samples
- `openingMessage` — Tino greeting (usted)
- `defaultChips` — horizon / renta fija / liquidez

## Mock chat (`VITE_ADVISOR_MOCK=true`)

`apps/web/src/services/advisor-mock.ts` uses `scenarios.ts` to map user text to streamed responses.

| Intent keywords                  | Response                                       |
| -------------------------------- | ---------------------------------------------- |
| portafolio, cómo va, rendimiento | Portfolio summary + attribution (Rodrigo data) |
| por qué bajó, bajó, movió        | Fast attribution (Journey B)                   |
| parado, idle, tres millones      | Idle cash orientation + chips                  |
| peso, dólar, mercado             | Market context + citations                     |
| fondo, etf, renta fija           | Product list + chips                           |
| estructurado, nota               | Blocked product + handoff offer                |
| default                          | Capabilities hint                              |

## Switching to live API

Set in `apps/web/.env`:

```env
VITE_ADVISOR_MOCK=false
```

Ensure `apps/agent` runs on port 8000 (Vite proxies `/api`).

## Adding a scenario

1. Add data to `fixtures/rodrigo.ts` if new entities are needed
2. Register intent matcher in `scenarios.ts`
3. Return `{ speech, uiPayload[], chips? }` using contract `UIComponent` types
4. Keep exact figures out of `speech` (split-channel rule)
