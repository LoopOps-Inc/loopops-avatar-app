# services/agent

Placeholder reserved for the agent backend (Python 3.12 / FastAPI / LangGraph
with Gemini), following the reference architecture in the sibling repo
`actinver-ai-advisor` (see its `services/agent` and `docs/01-architecture`).

The frontend lives in `apps/web` and expects this service to expose the
conversational API (chat + voice orchestration, portfolio Q&A, suitability
gate, form specs). Until it exists, the web app runs standalone in sandbox
mode through the Vite dev proxy.

Owned by the backend developer — scaffold it from the reference repo.
