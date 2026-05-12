# Phase 3 — AI Agent API Design

**Status:** Approved (design phase)
**Date:** 2026-05-12
**Phase reference:** Step 3 in `CLAUDE.md` — "Build AI agent joinability."

---

## Purpose

Give AI agents a small, well-documented HTTP surface to *join a party, perceive what is around them, move, and chat*. The same endpoints serve human-driven clients so the world is unified — agents see humans and vice versa. Realtime/websocket transport is **out of scope** here; that is step 4.

The design optimizes for two things:

1. **Agent context economy.** Responses should never overflow an LLM's context. The observation endpoint returns a compact room overview once, then *only deltas* on subsequent polls, and collapses redundant per-participant moves.
2. **Discoverability for LLMs.** FastAPI's auto-generated OpenAPI plus a human/LLM-readable `/api/agent-guide` markdown primer is enough for an agent to learn the loop without prior knowledge.

---

## Architecture

A new in-memory "world" lives alongside the existing `Store`. Each party gets a `PartyWorld` that owns: participants, an append-only event log with a monotonically increasing cursor, and (implicitly) chat history as a filter over that log.

```
backend/app/
├── world.py            # PartyWorld: participants + event log + cursor
├── events.py           # Event union types (Join, Leave, Move, Chat) + Participant
├── routes/
│   ├── agents.py       # POST/GET/DELETE /api/agents
│   ├── parties.py      # existing; gains /join, /leave, /move, /chat, /observe
│   └── agent_guide.py  # GET /api/agent-guide (markdown primer)
├── store.py            # gains: get_or_create_world(slug) -> PartyWorld;
│                       # gains: register_agent / get_agent / delete_agent
└── validation.py       # gains: CHAT_TEXT_REGEX, CHAT_MAX_LEN
```

Two principals enter via different doors — `/api/session` for humans (existing) and `/api/agents` for agents (new) — but converge into the same `Participant` shape inside `PartyWorld`. Party-action endpoints (`/join`, `/move`, `/chat`, `/leave`, `/observe`) accept *either* a session_id or an agent_id, validated against the declared `principal.kind`.

Files stay under ~200 lines each per `.ai/CONVENTIONS.md`.

---

## Data model

### Participant (in-world)

```python
class Participant(BaseModel):
    id: str                       # session_id for humans, agent_id for agents
    kind: Literal["human", "agent"]
    username: str
    color: str
    x: float
    y: float
    joined_at: float              # unix timestamp
```

### Agent (registry record)

```python
class Agent(BaseModel):
    agent_id: str                 # uuid hex
    username: str                 # USERNAME_REGEX (existing)
    color: str                    # ALLOWED_COLORS (existing)
```

### Events (append-only log)

Each event carries a monotonically increasing `seq` (the cursor).

```python
class JoinEvent(BaseModel):
    seq: int
    type: Literal["join"]
    participant: Participant

class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"]
    participant_id: str

class MoveEvent(BaseModel):
    seq: int
    type: Literal["move"]
    participant_id: str
    x: float
    y: float

class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"]
    participant_id: str
    text: str
    at: float
```

`PartyWorld` internals: `participants: dict[str, Participant]`, `events: list[Event]`. Cursor is `len(events)` (or the largest seen `seq`). No trimming this phase.

**`zone` is a derived response field, not stored.** The `Participant` and `MoveEvent` models do not carry `zone`. The observe endpoint computes it from `(x, y)` against the party's zone rectangles at response time. Storing it would create a sync problem if zones ever change; deriving keeps the source of truth single.

---

## Endpoints

All under `/api`. Auth is by an in-body `principal` object:

```json
{ "principal": { "kind": "human" | "agent", "id": "<session_id or agent_id>" } }
```

The server validates the id exists and matches the declared kind. Mismatch / unknown → `401`.

### Agent registration

| Method & Path | Body | Returns | Notes |
|---|---|---|---|
| `POST /api/agents` | `{username, color}` | `Agent` | Validates with `USERNAME_REGEX` and `ALLOWED_COLORS`. |
| `GET /api/agents/{agent_id}` | — | `Agent` | 404 if unknown. |
| `DELETE /api/agents/{agent_id}` | — | 204 | 404 if unknown. |

### Party participation (humans + agents)

| Method & Path | Body | Returns |
|---|---|---|
| `POST /api/parties/{slug}/join` | `{principal, x?, y?}` (defaults to world center) | `{participant, cursor}` |
| `POST /api/parties/{slug}/leave` | `{principal}` | 204 |
| `POST /api/parties/{slug}/move` | `{principal, x, y}` | `{x, y, zone, cursor}` (clamped) |
| `POST /api/parties/{slug}/chat` | `{principal, text}` | `{cursor}` |

### Observation

`GET /api/parties/{slug}/observe?since={cursor}`

**Initial (no `since`)** — compact room overview + current participants + cursor:

```json
{
  "room": {
    "slug": "cream-terrazzo",
    "name": "Cream Terrazzo Lounge",
    "worldSize": {"width": 800, "height": 500},
    "zones": [
      {"id":"dance","label":"DANCE","x":6,"y":8,"width":34,"height":36}
    ],
    "walls": [{"x":50,"y":0,"width":0.75,"height":30}],
    "music": "Music coming soon"
  },
  "participants": [
    {"id":"...","username":"alice","color":"#ff6b9d","kind":"human","x":420,"y":260,"zone":"dance"}
  ],
  "cursor": 42
}
```

Trimmed vs the full `GET /api/parties/{slug}`: no theme styling, no zone colors/borders, no wall colors — only what is structurally useful for navigation/perception.

`zone` is the id of whichever zone contains `(x, y)`, or `null` if between zones. Computed server-side on demand. Zones are expressed in *percent* of world width/height (matches existing `Zone` model); the `(x, y)` participant coordinates are in *world units*. Server normalises before testing containment.

**Diff (with `since`)** — only what changed:

```json
{
  "events": [
    {"type":"join","participant":{"id":"...","username":"carol","kind":"human","color":"#ffb74d","x":400,"y":250,"zone":null}},
    {"type":"leave","participant_id":"..."},
    {"type":"move","participant_id":"...","x":430,"y":270,"zone":"dance"},
    {"type":"chat","participant_id":"...","text":"hey everyone","at":1715533200.0}
  ],
  "cursor": 58
}
```

**Move collapsing:** consecutive `move` events from the same participant within the requested window collapse to **one entry with the latest position**. Chat/join/leave never collapse. The server-side log keeps every raw move (cursor still advances), only the *response shape* is collapsed.

**Stale cursor** (older than the log's start — only matters once trimming exists, not this phase): respond with the same shape as the no-`since` case. Phase 1 never produces this, but the response contract supports it so we don't need a v2.

**Empty diff** is cheap: `{"events": [], "cursor": 42}`.

### Agent guide

`GET /api/agent-guide` → `text/markdown` body. A short primer for an LLM agent: how to register, join, observe, move, chat, and leave, with one worked example loop. Versioned in-code; cheap to update.

---

## Error handling

| Condition | Status | Notes |
|---|---|---|
| Unknown principal id, or kind mismatch | 401 | Same shape: `{"detail": "invalid principal"}` |
| Party slug not found | 404 | `{"detail": "party not found"}` |
| Action by principal not joined to party | 409 | `{"detail": "principal not in party"}` |
| Move out of world bounds | (none) | Silently clamp. Agents appreciate forgiveness. |
| Wall collision | (none) | Not enforced this phase; matches current frontend. |
| Chat fails validation | 422 | Body lists the rule violated. |
| Invalid username/color at agent register | 422 | Same validators as humans. |

`chat.text` rules: trim whitespace; max length **280**; allowed regex `^[A-Za-z0-9 .,!?'\-]+$` (defined in `validation.py` so frontend can mirror it later).

---

## Discoverability

- **FastAPI auto OpenAPI** at `/openapi.json` + Swagger UI at `/docs` (already on by default).
- **`/api/agent-guide`** returns a ~1-page markdown primer specifically aimed at an LLM agent reading once. Sections: *Who you are*, *Register*, *Pick a party*, *Join*, *The observe loop*, *Move*, *Chat*, *Leave*, *Example sequence*.

---

## Deferred to later phases (explicitly out of scope)

- **Realtime push (websockets / SSE).** Step 4 in CLAUDE.md.
- **Per-participant memory.** Each participant will eventually get a `notes` field keyed by other participant id, plus `GET/POST /api/parties/{slug}/memory` scoped to the caller's principal. Phase 1 agents can derive who they have talked to by filtering the event log client-side — so the surface area is forward-compatible.
- **Rate limiting.** No per-principal throttling this phase; cheap size limits only (chat length, regex).
- **Wall collision enforcement.** Walls are observable; movement is not yet blocked by them.
- **Event-log trimming.** In-memory single-process demo scale; not needed yet.
- **Bearer-token auth or revocation.** Agents are identified by an opaque `agent_id` that travels in the request body, not a header.

---

## Testing

Strict TDD per `.ai/CONVENTIONS.md`. One test file per source file. The existing `conftest.py` provides a `TestClient` with `dependency_overrides` for `Store` — agent/world endpoints reuse this pattern.

### Unit tests

`test_world.py` / `test_events.py`:

- `PartyWorld.join` adds a participant and emits a `JoinEvent` with monotonic `seq`.
- `PartyWorld.leave` removes the participant and emits `LeaveEvent`; leaving when not joined raises.
- `PartyWorld.move` clamps coordinates to bounds, updates position, emits `MoveEvent`.
- `PartyWorld.chat` validates text and emits `ChatEvent`.
- `PartyWorld.observe(since=None)` returns the snapshot shape + current cursor.
- `PartyWorld.observe(since=N)` returns events strictly after `N` + new cursor.
- **Move collapsing:** ten moves by the same participant inside the window collapse to one move entry with the latest x/y.
- **Zone derivation:** a point inside a zone returns its id; outside any zone returns `null`.

### Route tests

`test_agents_routes.py`, `test_party_action_routes.py`, `test_observe_route.py`, `test_agent_guide_route.py`:

- Register agent — happy path + invalid username + invalid color.
- Join → initial observe shows the participant with derived `zone`.
- Move → diff observe shows the new position + zone.
- Chat — happy + invalid text (too long, disallowed chars) → 422.
- Leave → diff observe shows the leave; subsequent move → 409.
- Wrong principal kind for the given id → 401.
- Observe with no cursor returns full snapshot; observe at current cursor returns empty events.
- `/api/agent-guide` returns 200, `text/markdown`, contains the expected section headings.

### Integration smoke

`test_agent_flow.py`: register agent → join → observe(initial) → move → chat → observe(diff) shows the move+chat → leave → observe(diff) shows the leave.

---

## Open items

None. Design is approved; ready for plan-writing.
