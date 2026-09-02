# GEMINI.md — LoopOps Avatar App

Shared coding rules: [`AGENTS.md`](./AGENTS.md). Knowledge index: [`knowledge/README.md`](./knowledge/README.md).

This app uses **Gemini** as the LLM on the backend. When implementing agent tools or backend integration, follow LangChain / LangGraph patterns with explicit tool definitions (portfolio lookup, news scraping, risk-tier products, etc.).

## Writing style

Canonical: [`knowledge/writing-style.md`](./knowledge/writing-style.md). Mirror: `.cursor/rules/writing-style.mdc`.

Apply to user-facing copy (i18n, empty states, toasts, modals), knowledge docs, README, PR descriptions, and commit messages. Do not apply to code identifiers or file paths.

## Before you code

| File                              | Read before…                                         |
| --------------------------------- | ---------------------------------------------------- |
| `knowledge/architecture.md`       | Any structural change, new feature, backend contract |
| `knowledge/chat-and-voice.md`     | Chat UI, voice mode, streaming, session history      |
| `knowledge/heygen-live-avatar.md` | Avatar video, WebRTC, session lifecycle              |
| `knowledge/design-system.md`      | Components, tokens, semantic utilities               |
| `knowledge/writing-style.md`      | User-facing copy                                     |

After completing a new feature, ask: **"Would you like me to document this in `knowledge/`?"**
