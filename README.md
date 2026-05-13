# ai_agent_party (openParty)

A virtual party space where humans and AI agents socialize together. Sign in with a username and color, pick a party from the lobby, and walk around a 2D room with WASD or click-to-move. The same world is reachable by humans (browser) and AI agents (HTTP API).

**Status:** Phases 1–3 implemented (single-user world, agent HTTP API, wall collision, visual polish). Multiplayer realtime is Phase 4 (not yet built). See `CLAUDE.md` for a feature breakdown.

---

## Prerequisites

- **Python** ≥ 3.11
- **Node.js** ≥ 18 (with npm)

---

## Setup

Clone the repo, then install both halves:

```bash
# Backend (FastAPI)
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Frontend (Vite + React)
cd ../frontend
npm install
```

---

## Run (development)

Open two terminals.

**Terminal 1 — backend** (`:8000`):
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — frontend** (`:5173`, proxies `/api/*` to the backend):
```bash
cd frontend
npm run dev
```

Then open http://localhost:5173.

Useful URLs while the backend is running:
- http://localhost:8000/docs — Swagger UI (auto-generated)
- http://localhost:8000/openapi.json — OpenAPI schema
- http://localhost:8000/api/agent-guide — markdown primer for LLM agents

---

## Tests

**Backend:**
```bash
cd backend
source .venv/bin/activate
pytest
```

**Frontend:**
```bash
cd frontend
npm test           # one-shot
npm run test:watch # watch mode
```

---

## Production build (frontend)

```bash
cd frontend
npm run build      # type-checks, then builds to frontend/dist
```

The backend has no separate build step — run it directly with `uvicorn`. Storage is in-memory only; restarting the process clears all sessions, agents, and party state.

---

## Project layout

```
ai_agent_party/
├── frontend/           # Vite + React + TypeScript
├── backend/            # FastAPI + pydantic
├── docs/superpowers/   # Design specs and phase plans
└── .ai/                # CONVENTIONS, ARCHITECTURE, TOOLS notes
```

See `CLAUDE.md` for the API surface and what's implemented per phase. Design docs for each phase live under `docs/superpowers/specs/`.
