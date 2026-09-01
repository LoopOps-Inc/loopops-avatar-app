# Product context — Tino POC

## What Tino is

**Tino** is a video-avatar wealth advisor inside the Actinver app. Face and voice on screen, chat stream layered on top. He explains the portfolio, explores products, prepares forms, and hands off to the human advisor when needed.

Working name only. Final branding is out of POC scope.

## POC scope (three screens)

1. **Explorar** — entry card _Consulta con un asesor_ with **Agendar consulta** and **Habla con Tino**
2. **Chat modal** — avatar behind, chat on top, suggestion chips, composer
3. **Full-screen modal** — prefilled forms and signature when the flow needs room

Five features in scope: avatar (F1), portfolio insight (F2), product exploration (F3), forms (F4), human handoff (F5).

Out of scope: trade execution, market prediction, tax/legal advice, voice input, English, desktop.

## Primary persona — Rodrigo

- 49, Zapopan. Business owner. Profile **moderado** (last reviewed 3 years ago).
- ~MXN 14.5M with Actinver: CETES ladder, debt funds, NAFTRAC, **MXN 3M idle** in _cuenta_ since a property sale.
- Assigned advisor: **Fernanda Ruvalcaba** (must be named in product, never "un asesor").
- Wants explanation before recommendation. Asks at night without feeling judged.

## Secondary persona — Fernanda

- Patrimonial advisor, Guadalajara. ~180 clients. Fears Tino replaces her; design must position him as her extension.
- Receives a **briefing** on handoff: question, products explored, simulations, blocked suggestions.

## The razonabilidad guardrail

Tino operates under **Actinver WM Asesor Patrimonial** (CNBV-registered _asesor en inversiones_). Personalized suggestions require:

1. Deterministic congruence check between _perfil del inversionista_ and _perfil del producto_
2. **Justification card** on screen (non-dismissible) when a suggestion passes
3. **Plain block + reason** when it fails, never silent hiding
4. Audit record before the client sees the output

For POC mocks: model the justification card and blocked-product states in FE data even before the backend gate exists.

## Product principle

> Tino explains, explores, prepares and hands off. He does not execute, predict, or improvise.

## Copy register

- **es-MX**, **usted** (warm professional, not familiar)
- State limits in the opening greeting
- Answer anxiety, not only the number
- Never upsell after a "why did it drop?" question

Opening message (POC):

> "Hola, soy Tino. Le ayudo a entender su portafolio, explorar instrumentos y preparar lo que necesite firmar. No ejecuto operaciones ni predigo mercados — para eso está Fernanda, su asesora. ¿Qué le gustaría revisar hoy?"

## Team split (this repo)

| Team         | Owns                                                                        |
| ------------ | --------------------------------------------------------------------------- |
| **Backend**  | LiveAvatar LITE, agent stream, DB, razonabilidad gate, audit                |
| **Frontend** | UI, mock domain data, conversation flows against fixtures until API is live |
