# Storyboard and journeys

## Screen 1 — Explorar (home)

**Header:** Actinver Trade branding, notifications, user initials (**DR**).

**Portfolio card (storyboard values for POC UI):**

| Field         | Value             |
| ------------- | ----------------- |
| Total         | $948,250.00 MXN   |
| Period change | −2.4%             |
| Day change    | +$1,032 MXN       |
| Sparkline     | Small trend chart |

**Consulta con un asesor card** (both actions equal weight):

- _Agendar consulta_
- **Habla con Tino** → opens chat modal

**Mis posiciones (sample rows):**

| Instrument | Value      | Change |
| ---------- | ---------- | ------ |
| CETES 28d  | $15,200.00 | +1.2%  |
| ACTIREN    | $23,050.00 | +0.8%  |
| NAFTRAC    | $10,000.00 | +3.5%  |

**Bottom nav:** Explorar · Portafolio · AV · Retiro

> Persona doc uses MXN 14.5M total and MXN 3M idle cash for conversation depth. Storyboard uses a simplified portfolio card. Mocks include both: `explorarSummary` for the home screen, `fullProfile` for advisor dialogue.

---

## Screen 2 — Chat with Tino

**Layout:** Avatar video upper region. Chat sheet over lower portion with drag handle.

**Header:** `Consulta con Tino`, back, delete conversation.

**Opening (Tino):** scope + limits + named advisor (see product-context.md).

**Example user message:** _"ETFs de deuda de bajo riesgo"_

**Suggestion chips (max 4, single line):**

- `Horizonte 1–3 años`
- `Renta fija`
- `Liquidez diaria`

Chips collect _perfil_ inputs conversationally (horizon, asset class, liquidity).

**Avatar states:** idle · listening · speaking · thinking (visible within 400ms of send).

**Text-only fallback:** always available; auto-fallback if video fails.

---

## Screen 3 — Full-screen modal

Used for forms, contracts, signature. Back returns to chat with state preserved.

POC placeholder: prefilled fields, key terms above fold, signature area, confirm.

---

## Journey A — "El dinero parado" (primary demo arc)

**Trigger:** MXN 3M idle since March, 10:40pm Tuesday.

| Beat     | Tino behaviour                                                    |
| -------- | ----------------------------------------------------------------- |
| Orient   | Confirm amount, idle duration, inflation cost                     |
| Ask      | Horizon and purpose (university abroad, USD, 14 months)           |
| Explain  | Split earmarked vs discretionary cash (F2)                        |
| Explore  | 2–3 product cards + one ineligible with reason (F3)               |
| Simulate | Liquidity and risk profile mechanics, no projected returns        |
| Suggest  | One option with **justification card** (FR-0.2)                   |
| Block    | Structured note fails razonabilidad — show reason, offer Fernanda |
| Form     | Full-screen modal, prefilled, sign (F4)                           |
| Handoff  | Remaining MXN 1.2M → schedule Fernanda with briefing (F5)         |

**Target elapsed:** ~11 minutes same evening.

---

## Journey B — "¿Por qué bajó?" (habit builder)

**Trigger:** Headline, 6:40am, sees −2.8%.

| Requirement                                                 |
| ----------------------------------------------------------- |
| Fast attribution: which holdings, proportion, cited reasons |
| Frame against _his_ horizon, not a generic index            |
| No upsell at the end                                        |

---

## Journey C — Out of scope handoff

Life events (sale, inheritance, health). Tino detects early, no product cards, offers Fernanda with briefing.

---

## Alignment checklist (FE)

1. Explain before offer
2. Suggestion always has justification card (or block card)
3. Blocked products shown with reason
4. Citations openable; `as_of` on every figure
5. Fernanda named and reachable
6. Flow works in text-only mode
