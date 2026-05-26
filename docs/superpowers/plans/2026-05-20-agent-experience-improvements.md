# Agent Experience Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the prioritized fixes from `docs/superpowers/specs/2026-05-20-agent-experience-improvements.md` so a first-time agent can fully interact with notes, drawboards, reactions, and chat using only API responses and the agent guide — no source-reading required.

**Architecture:** Three backend surface changes — error envelopes gain `allowed_*` lists; initial `/observe` snapshot gains `recent_chat`; event payloads gain `actor_username`/`actor_kind` (and `actor_id` aliases on `move`/`chat` so consumers can standardize). The agent guide is rewritten to list every allow-list inline, document module response shapes, and include "approaching a participant" and "reactive loop" worked examples. No frontend behavior changes — only additive fields and docs.

**Tech Stack:** FastAPI (Python 3.11) backend with pytest + httpx tests. TypeScript types updated where needed to stay in sync with new optional fields.

---

## Spec → Task Map

| Spec § | Task |
|---|---|
| 1.1 sticky `allowed_colors` in error | Task 2 |
| 1.2/1.3 stroke `width`/`color` enum + allow-list in error | Task 3 |
| 1.4 keep emoji allow-list copy-pasteable | Task 4 (consistency: add to error envelope too) |
| 1.5 module distance hint | NOT IN SCOPE — defer, called out as "polish" in spec §4 |
| 2.1 `room.modules` vs top-level `modules` | Task 8 (guide clarification only — non-breaking) |
| 2.2 event-shape standardization | Task 5 |
| 2.3 notes/strokes in initial snapshot | Task 7 (verify already present + lock with test) |
| 2.4 recent chat in initial snapshot | Task 6 |
| 3.1 approach-a-participant pattern | Task 8 (guide) |
| 3.2 reactive loop pattern | Task 8 (guide) |
| 3.3 module response shapes | Task 8 (guide) |
| 4-#7 unified color palette | DEFERRED — spec §4 marks low-medium, behavior change |

---

## File Structure

**Backend — modify:**
- `backend/app/routes/module_notes.py` — include `allowed_colors` in `invalid_note` 422.
- `backend/app/routes/module_drawboard.py` — include `allowed_colors`/`allowed_widths` in `invalid_stroke` 422.
- `backend/app/routes/reactions.py` — include `allowed_emojis` in `invalid_emoji` 422 for parity.
- `backend/app/events.py` — add optional `actor_username`/`actor_kind` to `Join/Leave/Move/Chat/Reaction` events.
- `backend/app/world.py` — populate the new fields when constructing events; expose `recent_chat(n)` helper.
- `backend/app/routes/party_actions.py` — include `recent_chat` in initial `/observe` snapshot.
- `backend/app/routes/agent_guide.py` — rewrite the guide; list allow-lists inline; add module response shapes, approach pattern, and reactive-loop worked example.

**Backend — new tests:**
- `backend/tests/test_module_notes_error_body.py`
- `backend/tests/test_module_drawboard_error_body.py`
- `backend/tests/test_reactions_error_body.py`
- `backend/tests/test_observe_recent_chat.py`
- `backend/tests/test_observe_initial_modules_state.py`
- `backend/tests/test_event_actor_fields.py`
- `backend/tests/test_agent_guide_content.py`

**Frontend — modify:**
- `frontend/src/api/types.ts` — add optional `actor_username?`/`actor_kind?` to event types; add optional `recent_chat?` to initial observe response.

**Frontend — new tests:**
- `frontend/tests/types.compile.test.ts` is unnecessary — the optional fields are purely additive and existing call sites compile unchanged. The vitest suite for `useRealtimeParty` will exercise them.

---

## Task 1: Pre-flight — confirm baseline tests pass

**Files:** none (read-only)

- [ ] **Step 1: Run backend test suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS (baseline before any change).

- [ ] **Step 2: Run frontend test suite**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS.

- [ ] **Step 3: Commit nothing — record baseline only**

If anything fails on `main` of `feat/modules`, STOP and report. Do not attempt to fix unrelated failures as part of this plan.

---

## Task 2: `invalid_note` error body gains `allowed_colors`

**Files:**
- Modify: `backend/app/routes/module_notes.py`
- Test: `backend/tests/test_module_notes_error_body.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_module_notes_error_body.py`:

```python
from app.validation import STICKY_COLOR_ALLOWLIST
from tests.conftest import join_party, register_human


def test_invalid_note_color_returns_allowed_colors(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    # Walk to the sticky module zone via the snapshot
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in obs["modules"] if m["kind"] == "stickynotes")
    ir = sticky["interactionRect"]
    cx = ir["x"] + ir["w"] / 2
    cy = ir["y"] + ir["h"] / 2
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": sess["principal"], "x": cx, "y": cy},
    )

    resp = client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={
            "principal": sess["principal"],
            "text": "hi",
            "color": "#9c27b0",  # not in sticky allow-list
            "x": 10,
            "y": 10,
        },
    )
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"] == "invalid_note"
    assert body["allowed_colors"] == list(STICKY_COLOR_ALLOWLIST)
```

If `tests/conftest.py` lacks `register_human` / `join_party` helpers, inline the registration + join calls; check the existing conftest first.

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd backend && python -m pytest tests/test_module_notes_error_body.py -v`
Expected: FAIL — body is missing `allowed_colors` key.

- [ ] **Step 3: Implement**

In `backend/app/routes/module_notes.py`, import the allow-list and pass it into the error envelope. Replace the `NoteValidationError` branch of `_map_world_errors`:

```python
from app.validation import STICKY_COLOR_ALLOWLIST, NoteValidationError
# ... in _map_world_errors:
    return HTTPException(
        status_code=422,
        detail=envelope(
            "invalid_note",
            message=str(exc),
            allowed_colors=list(STICKY_COLOR_ALLOWLIST),
        ),
    )
```

(Leave the other branches unchanged.)

- [ ] **Step 4: Re-run test, confirm pass**

Run: `cd backend && python -m pytest tests/test_module_notes_error_body.py -v`
Expected: PASS.

- [ ] **Step 5: Run full backend suite to confirm no regression**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/module_notes.py backend/tests/test_module_notes_error_body.py
git commit -m "feat(notes): include allowed_colors in invalid_note 422 body"
```

---

## Task 3: `invalid_stroke` error body gains `allowed_colors` + `allowed_widths`

**Files:**
- Modify: `backend/app/routes/module_drawboard.py`
- Test: `backend/tests/test_module_drawboard_error_body.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_module_drawboard_error_body.py`:

```python
from app.validation import STROKE_COLOR_ALLOWLIST, STROKE_WIDTH_ALLOWLIST


def _join_at_drawboard(client):
    from tests.conftest import register_human, join_party  # adapt if helper absent
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    draw = next(m for m in obs["modules"] if m["kind"] == "drawboard")
    ir = draw["interactionRect"]
    cx = ir["x"] + ir["w"] / 2
    cy = ir["y"] + ir["h"] / 2
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": sess["principal"], "x": cx, "y": cy},
    )
    return sess, draw


def test_invalid_stroke_color_returns_allowlists(client):
    sess, draw = _join_at_drawboard(client)
    resp = client.post(
        f"/api/parties/cream-terrazzo/modules/{draw['id']}/strokes",
        json={
            "principal": sess["principal"],
            "color": "#abcabc",  # not in stroke allow-list
            "width": "med",
            "points": [{"x": 1, "y": 1}],
        },
    )
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"] == "invalid_stroke"
    assert body["allowed_colors"] == list(STROKE_COLOR_ALLOWLIST)
    assert body["allowed_widths"] == list(STROKE_WIDTH_ALLOWLIST)


def test_invalid_stroke_width_returns_allowlists(client):
    sess, draw = _join_at_drawboard(client)
    resp = client.post(
        f"/api/parties/cream-terrazzo/modules/{draw['id']}/strokes",
        json={
            "principal": sess["principal"],
            "color": STROKE_COLOR_ALLOWLIST[0],
            "width": "huge",
            "points": [{"x": 1, "y": 1}],
        },
    )
    # Pydantic catches the Literal-typed field as 422 itself; the API guarantee
    # we're testing is for the world-level validator. If pydantic rejects this
    # at the boundary the route never reaches our envelope. So either:
    # - relax the route model so we hit the envelope (preferred for agents), OR
    # - assert pydantic's 422 shape stays usable.
    # We expect the route schema to be relaxed in this task so agents see one
    # consistent error envelope.
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"] == "invalid_stroke"
    assert body["allowed_widths"] == list(STROKE_WIDTH_ALLOWLIST)
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd backend && python -m pytest tests/test_module_drawboard_error_body.py -v`
Expected: FAIL — body lacks `allowed_colors`/`allowed_widths`, and width 422 fails before reaching the envelope.

- [ ] **Step 3: Implement**

In `backend/app/routes/module_drawboard.py`:

1. Relax `StrokeRequest.width` from `Literal[...]` to `str` so the in-world validator runs (giving us the uniform envelope shape).
2. Import the allow-lists and inject them into the envelope.

```python
from app.validation import (
    STROKE_COLOR_ALLOWLIST,
    STROKE_WIDTH_ALLOWLIST,
    StrokeValidationError,
)
# ...
class StrokeRequest(BaseModel):
    principal: Principal
    color: str
    width: str
    points: list[dict]

# in _map_errors:
    if isinstance(exc, StrokeValidationError):
        return HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_stroke",
                message=str(exc),
                allowed_colors=list(STROKE_COLOR_ALLOWLIST),
                allowed_widths=list(STROKE_WIDTH_ALLOWLIST),
            ),
        )
```

- [ ] **Step 4: Re-run test, confirm pass**

Run: `cd backend && python -m pytest tests/test_module_drawboard_error_body.py -v`
Expected: PASS.

- [ ] **Step 5: Run full backend suite to confirm no regression**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS (in particular `test_modules_coverage.py` width-rejection tests should still pass — they assert the error code, not the schema-level rejection).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/module_drawboard.py backend/tests/test_module_drawboard_error_body.py
git commit -m "feat(drawboard): include allowed_colors/allowed_widths in invalid_stroke 422"
```

---

## Task 4: `invalid_emoji` error body gains `allowed_emojis` (parity)

**Files:**
- Modify: `backend/app/routes/reactions.py`
- Test: `backend/tests/test_reactions_error_body.py`

- [ ] **Step 1: Write the failing test**

```python
from app.validation import REACTION_EMOJI_ALLOWLIST


def test_invalid_emoji_returns_allowed_emojis(client):
    from tests.conftest import register_human, join_party
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": sess["principal"], "emoji": "🦄"},
    )
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"] == "invalid_emoji"
    assert body["allowed_emojis"] == list(REACTION_EMOJI_ALLOWLIST)
```

- [ ] **Step 2: Run the test, confirm it fails**

Run: `cd backend && python -m pytest tests/test_reactions_error_body.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `backend/app/routes/reactions.py`:

```python
from app.validation import REACTION_EMOJI_ALLOWLIST, ReactionValidationError
# ...
    except ReactionValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_emoji",
                message=str(exc),
                allowed_emojis=list(REACTION_EMOJI_ALLOWLIST),
            ),
        )
```

- [ ] **Step 4: Re-run test, confirm pass**

Run: `cd backend && python -m pytest tests/test_reactions_error_body.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/reactions.py backend/tests/test_reactions_error_body.py
git commit -m "feat(reactions): include allowed_emojis in invalid_emoji 422 body"
```

---

## Task 5: Standardize event shape — add `actor_username` + `actor_kind` (and `actor_id` alias)

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/world.py`
- Modify: `frontend/src/api/types.ts`
- Test: `backend/tests/test_event_actor_fields.py`

**Design decision:** Existing fields (`participant_id` on move/chat/leave; `actor_id` on reaction; nested `participant` on join) stay untouched for backwards compat. Each event gains optional `actor_username` and `actor_kind`. `MoveEvent`/`ChatEvent`/`LeaveEvent` additionally gain `actor_id` (mirror of `participant_id`) so agents can read one consistent key. `JoinEvent` exposes `actor_id`/`actor_username`/`actor_kind` via the existing `_participant_dict` projection used by snapshots/observe (no schema change needed).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_event_actor_fields.py`:

```python
from tests.conftest import register_human, join_party


def test_move_event_carries_actor_fields(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")
    # Bob takes the cursor; Alice moves.
    cur = client.get(f"/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": a["principal"], "x": 123.0, "y": 45.0},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    moves = [e for e in diff["events"] if e["type"] == "move"]
    assert moves, "expected at least one move event"
    mv = moves[-1]
    assert mv["actor_id"] == mv["participant_id"]  # alias present
    assert mv["actor_username"] == "Alice"
    assert mv["actor_kind"] == "human"


def test_chat_event_carries_actor_fields(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": a["principal"], "text": "hello"},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    chat = [e for e in diff["events"] if e["type"] == "chat"][-1]
    assert chat["actor_id"] == chat["participant_id"]
    assert chat["actor_username"] == "Alice"
    assert chat["actor_kind"] == "human"


def test_reaction_event_carries_actor_username(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": a["principal"], "emoji": "🔥"},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    rx = [e for e in diff["events"] if e["type"] == "reaction"][-1]
    assert rx["actor_id"]  # already present
    assert rx["actor_username"] == "Alice"
    assert rx["actor_kind"] == "human"


def test_leave_event_carries_actor_fields(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": a["principal"]},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    lv = [e for e in diff["events"] if e["type"] == "leave"][-1]
    assert lv["actor_id"] == lv["participant_id"]
    assert lv["actor_username"] == "Alice"
    assert lv["actor_kind"] == "human"
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_event_actor_fields.py -v`
Expected: FAIL — new fields missing from event dumps.

- [ ] **Step 3: Extend the event models**

In `backend/app/events.py`, add optional fields. Keep existing fields:

```python
class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"] = "leave"
    participant_id: str
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None


class MoveEvent(BaseModel):
    seq: int
    type: Literal["move"] = "move"
    participant_id: str
    x: float
    y: float
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None


class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    participant_id: str
    text: str
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None


class ReactionEvent(BaseModel):
    seq: int
    type: Literal["reaction"] = "reaction"
    actor_id: str
    emoji: str
    expires_at: float
    at: float
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
```

- [ ] **Step 4: Populate the new fields at construction**

In `backend/app/world.py`, find every place an event is constructed and pass actor fields from the live `Participant`. For `LeaveEvent`, capture the participant **before** deleting from `self.participants`.

Add a private helper:

```python
def _actor_fields(self, participant_id: str) -> dict:
    p = self.participants.get(participant_id)
    if p is None:
        return {}
    return {
        "actor_id": p.id,
        "actor_username": p.username,
        "actor_kind": p.kind,
    }
```

Then in:
- `leave`: capture `p = self.participants[participant_id]`, delete, then construct `LeaveEvent(..., actor_id=p.id, actor_username=p.username, actor_kind=p.kind)`.
- `move`: `MoveEvent(..., **self._actor_fields(participant_id))`.
- `chat`: `ChatEvent(..., **self._actor_fields(participant_id))`.
- `react`: `ReactionEvent(..., **self._actor_fields(participant_id))` (since `actor_id` is required already, just add username/kind).

- [ ] **Step 5: Run the new test, confirm pass**

Run: `cd backend && python -m pytest tests/test_event_actor_fields.py -v`
Expected: PASS.

- [ ] **Step 6: Run full backend suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS. If `test_observe_route.py` or similar asserts equality of event dicts without the new keys, update those assertions to use subset comparisons or ignore optional keys.

- [ ] **Step 7: Update frontend types**

In `frontend/src/api/types.ts`, add optional fields to the move/chat/leave/reaction event interfaces. (Open the file, find the existing event types, add `actor_id?: string`, `actor_username?: string`, `actor_kind?: 'human' | 'agent'` to each. Don't change required fields.)

- [ ] **Step 8: Frontend test pass**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS (no consumer is using the new fields yet — additive optionals).

- [ ] **Step 9: Commit**

```bash
git add backend/app/events.py backend/app/world.py \
        backend/tests/test_event_actor_fields.py \
        frontend/src/api/types.ts
git commit -m "feat(events): add actor_id/username/kind to move, chat, leave, reaction"
```

---

## Task 6: Initial `/observe` snapshot includes `recent_chat`

**Files:**
- Modify: `backend/app/world.py` (add `recent_chat` helper)
- Modify: `backend/app/routes/party_actions.py` (include in initial response)
- Test: `backend/tests/test_observe_recent_chat.py`

- [ ] **Step 1: Write the failing test**

```python
from tests.conftest import register_human, join_party


def test_initial_observe_includes_recent_chat(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    for i in range(3):
        client.post(
            "/api/parties/cream-terrazzo/chat",
            json={"principal": a["principal"], "text": f"hello {i}"},
        )
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    assert "recent_chat" in obs
    texts = [c["text"] for c in obs["recent_chat"]]
    assert texts == ["hello 0", "hello 1", "hello 2"]
    # carries actor fields so a late joiner can render "Alice: hello"
    for c in obs["recent_chat"]:
        assert c["actor_username"] == "Alice"
        assert c["actor_kind"] == "human"


def test_initial_observe_recent_chat_capped_at_20(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    for i in range(25):
        client.post(
            "/api/parties/cream-terrazzo/chat",
            json={"principal": a["principal"], "text": f"msg{i}"},
        )
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    assert len(obs["recent_chat"]) == 20
    # most recent retained
    assert obs["recent_chat"][-1]["text"] == "msg24"
    assert obs["recent_chat"][0]["text"] == "msg5"
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_observe_recent_chat.py -v`
Expected: FAIL — `recent_chat` key missing.

- [ ] **Step 3: Implement `recent_chat` on `PartyWorld`**

In `backend/app/world.py`, add a method (place near `snapshot`):

```python
RECENT_CHAT_LIMIT = 20  # module-level constant near other limits

def recent_chat(self, limit: int = 20) -> list[dict]:
    """Return up to `limit` most-recent ChatEvents, oldest-first."""
    out: list[dict] = []
    for ev in reversed(self._events):
        if isinstance(ev, ChatEvent):
            out.append(ev.model_dump())
            if len(out) >= limit:
                break
    out.reverse()
    return out
```

(Promote `RECENT_CHAT_LIMIT` to a top-level constant in `app/validation.py` for consistency with other limits, then import it. Optional but matches the file pattern.)

- [ ] **Step 4: Wire it into the initial observe response**

In `backend/app/routes/party_actions.py`, in `observe`:

```python
if since is None:
    snap = world.snapshot()
    return {
        "room": _room_view(party),
        "participants": snap["participants"],
        "cursor": snap["cursor"],
        "modules": snap["modules"],
        "lighting": snap["lighting"],
        "active_reactions": snap["active_reactions"],
        "recent_chat": world.recent_chat(20),
    }
```

- [ ] **Step 5: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_observe_recent_chat.py -v`
Expected: PASS.

- [ ] **Step 6: Run full backend suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 7: Update frontend types (optional field)**

In `frontend/src/api/types.ts`, add `recent_chat?: ChatEvent[]` to the initial observe response interface.

- [ ] **Step 8: Frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/world.py backend/app/routes/party_actions.py \
        backend/tests/test_observe_recent_chat.py frontend/src/api/types.ts
git commit -m "feat(observe): include recent_chat (last 20) in initial snapshot"
```

---

## Task 7: Lock in initial-snapshot module state with a regression test

**Files:**
- Test: `backend/tests/test_observe_initial_modules_state.py`

The current `snapshot()` already includes `notes` per sticky module and `strokes`/`vote` per drawboard. Spec §2.3 says this was missing; either it's been fixed or the spec is out of date. Lock the current behavior with an explicit test so a regression doesn't slip in.

- [ ] **Step 1: Write the test**

```python
from tests.conftest import register_human, join_party


def _move_into(client, sess, module):
    ir = module["interactionRect"]
    cx = ir["x"] + ir["w"] / 2
    cy = ir["y"] + ir["h"] / 2
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": sess["principal"], "x": cx, "y": cy},
    )


def test_initial_snapshot_contains_existing_notes_and_strokes(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")

    obs1 = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in obs1["modules"] if m["kind"] == "stickynotes")
    draw = next(m for m in obs1["modules"] if m["kind"] == "drawboard")

    _move_into(client, a, sticky)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={"principal": a["principal"], "text": "hi", "color": "yellow",
              "x": 10, "y": 10},
    )
    _move_into(client, a, draw)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{draw['id']}/strokes",
        json={"principal": a["principal"], "color": "#ffd54f",
              "width": "med", "points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]},
    )

    # Bob is a "late joiner" — gets the snapshot.
    b = register_human(client, username="Bob")
    join_party(client, b, "cream-terrazzo")
    obs2 = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky2 = next(m for m in obs2["modules"] if m["kind"] == "stickynotes")
    draw2 = next(m for m in obs2["modules"] if m["kind"] == "drawboard")
    assert len(sticky2["notes"]) == 1
    assert sticky2["notes"][0]["text"] == "hi"
    assert len(draw2["strokes"]) == 1
    assert len(draw2["strokes"][0]["points"]) == 2
```

- [ ] **Step 2: Run, confirm pass**

Run: `cd backend && python -m pytest tests/test_observe_initial_modules_state.py -v`
Expected: PASS immediately — this is documenting existing behavior. If it FAILS, snapshot is genuinely missing the data; in that case add `notes`/`strokes` to `_module_snapshot` in `world.py` (they should already be there per the current code; if absent, restore).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_observe_initial_modules_state.py
git commit -m "test(observe): lock in initial-snapshot notes/strokes per module"
```

---

## Task 8: Agent guide rewrite

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Test: `backend/tests/test_agent_guide_content.py`

The guide needs to (a) inline every allow-list (sticky colors, stroke colors, stroke widths, emojis), (b) document module response shapes (what `/notes` and `/strokes` POST return), (c) clarify the `room.modules` vs top-level `modules` duality, (d) add an "approaching a participant" pattern, (e) add a "reactive loop" worked example, (f) document the new `recent_chat` snapshot field and `actor_username`/`actor_kind` event fields.

- [ ] **Step 1: Write the failing test**

```python
def test_agent_guide_lists_sticky_color_allow_list(client):
    body = client.get("/api/agent-guide").text
    for c in ("yellow", "pink", "blue", "green"):
        assert c in body


def test_agent_guide_lists_stroke_width_enum(client):
    body = client.get("/api/agent-guide").text
    for w in ("thin", "med", "thick"):
        assert w in body


def test_agent_guide_lists_stroke_color_allow_list(client):
    from app.validation import STROKE_COLOR_ALLOWLIST
    body = client.get("/api/agent-guide").text
    for c in STROKE_COLOR_ALLOWLIST:
        assert c in body


def test_agent_guide_documents_module_response_shapes(client):
    body = client.get("/api/agent-guide").text
    # response contains the note/stroke object including its id
    assert "note.id" in body or "\"id\"" in body
    assert "cursor" in body


def test_agent_guide_has_approach_pattern(client):
    body = client.get("/api/agent-guide").text
    assert "Approaching" in body or "approach" in body.lower()
    assert "approachSlots" in body  # links to the data agents already have


def test_agent_guide_has_reactive_loop_example(client):
    body = client.get("/api/agent-guide").text
    assert "Reactive loop" in body or "reactive loop" in body.lower()


def test_agent_guide_documents_recent_chat_and_actor_fields(client):
    body = client.get("/api/agent-guide").text
    assert "recent_chat" in body
    assert "actor_username" in body
    assert "actor_kind" in body


def test_agent_guide_clarifies_room_vs_top_level_modules(client):
    body = client.get("/api/agent-guide").text
    # mentions both and tells the agent which one carries the live state
    assert "room.modules" in body
    assert "top-level" in body or "live" in body.lower()
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py -v`
Expected: FAIL on most assertions.

- [ ] **Step 3: Rewrite the guide**

Replace the `_GUIDE` body in `backend/app/routes/agent_guide.py`. Import all relevant allow-lists at the top and interpolate them as bullet lists, matching the existing `_COLOR_LIST` pattern:

```python
from app.validation import (
    ALLOWED_COLORS,
    REACTION_EMOJI_ALLOWLIST,
    STICKY_COLOR_ALLOWLIST,
    STROKE_COLOR_ALLOWLIST,
    STROKE_WIDTH_ALLOWLIST,
)

_COLOR_LIST = "\n".join(f"- `{c}`" for c in ALLOWED_COLORS)
_STICKY_COLOR_LIST = ", ".join(f"`{c}`" for c in STICKY_COLOR_ALLOWLIST)
_STROKE_COLOR_LIST = "\n".join(f"- `{c}`" for c in STROKE_COLOR_ALLOWLIST)
_STROKE_WIDTH_LIST = ", ".join(f"`{w}`" for w in STROKE_WIDTH_ALLOWLIST)
_EMOJI_LIST = " ".join(REACTION_EMOJI_ALLOWLIST)
```

Then update the `Modules` / `Sticky notes` / `Drawboard` / `Reactions` sections so each lists its allow-list inline, documents the response body (including `note.id` / `stroke.id` / `cursor`), and references `top-level modules` as the live state source.

Add two new sections after `## Example sequence`:

```markdown
## Locating modules in the observe response

`/observe` returns modules in two places:

- `room.modules` — **static** placement info (id, kind, position). Use this
  to know what modules exist.
- top-level `modules` — the **live** snapshot. Use this for
  `interactionRect`, `approachSlots`, current `notes`, `strokes`, and the
  current clear `vote` tally.

If you only read `room.modules` you will not see live state.

## Approaching a participant

Avatars do not collide with each other. To "stand next to" a human Mason at
`(mx, my)` without overlapping:

1. Pick a position 30-40 world units away on the same axis, e.g.
   `(mx + 36, my)` or `(mx, my + 36)`.
2. `POST /move` there.
3. Optionally `POST /react` with an emoji — this is the cheapest way to
   acknowledge the other participant.

For module interactions, prefer `approachSlots` from the live `modules`
array — it picks an unoccupied slot inside the `interactionRect` for you.

## Reactive loop pattern

The most life-like agent behavior is to mirror reactions back within ~2s:

```
GET /api/parties/{slug}/observe?since=<cursor>
  -> events: [{type: "reaction", actor_id: "X", emoji: "🔥", ...}]
POST /api/parties/{slug}/react
  { "principal": {...}, "emoji": "🔥" }
```

Every event now includes `actor_username` and `actor_kind` so you can
render `"<Mason> reacted with 🔥"` without keeping an id->name map. The
`move`, `chat`, and `leave` events also include `actor_id` as an alias for
`participant_id` so you can use a single key across event types.

## Joining late

The initial `/observe` snapshot (no `?since=`) now includes:

- `recent_chat` — up to the last 20 chat events with full actor info.
- `modules[*].notes` and `modules[*].strokes` — current board state.
- `active_reactions` — anyone reacting right now.

A late-joining agent has the same "room context" a human walking in has.
```

Make sure the `### Sticky notes` and `### Drawboard` sections list their allow-lists explicitly and call out the response shape, e.g.:

```markdown
### Sticky notes

Allowed `color`: {_STICKY_COLOR_LIST}.

`POST .../notes` body `{principal, text, color, x, y}` → 200
`{"note": {"id", "module_id", "author_id", "author_kind", "text",
"color", "x", "y", "created_at"}, "cursor"}`. Save `note.id` for later
PATCH/DELETE.

A bad color returns 422 with
`{detail: {error: "invalid_note", allowed_colors: [...]}}`.
```

…and similarly for drawboard (width enum + color allow-list inline; response shape with `stroke.id`).

- [ ] **Step 4: Re-run guide test**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py -v`
Expected: PASS.

- [ ] **Step 5: Run full backend suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS. (The existing `test_agent_guide_route.py` mostly checks status/content-type; surface changes should not break it.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_content.py
git commit -m "docs(agent-guide): list all allow-lists, add approach + reactive-loop patterns"
```

---

## Task 9: Final verification + CLAUDE.md note

**Files:**
- Modify: `CLAUDE.md` (one-line update to the "API Surface" / Phase notes)

- [ ] **Step 1: Full backend suite**

Run: `cd backend && python -m pytest --tb=short`
Expected: ALL PASS.

- [ ] **Step 2: Full frontend suite**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS.

- [ ] **Step 3: Spot-check the rendered guide**

Run: `cd backend && python -m uvicorn app.main:app --port 8901 &` then
`curl -s http://localhost:8901/api/agent-guide | head -120` and visually confirm the new sections render. Kill the server when done.

- [ ] **Step 4: Update CLAUDE.md "What's Implemented" with a short note**

Append to the modules section (or wherever phase notes live) a bullet:

```
- Agent-experience improvements (2026-05-20): allow-lists in error envelopes,
  recent_chat + initial module state in /observe, actor_username/kind on
  events, expanded agent guide.
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): note agent-experience improvements landed"
```

- [ ] **Step 6: Final summary commit log review**

Run: `git log --oneline main..HEAD`
Expected: a clean series of small commits, one per task. No fixup commits.

---

## Self-review checklist

1. **Spec coverage** — every numbered item in the spec maps to a task above (see Spec → Task Map at top). Items §1.5 and §4-#7 are explicitly deferred per spec §4/§5 priority guidance.
2. **No placeholders** — every code block has actual code; no "TODO"/"add error handling here".
3. **Type consistency** — `actor_id`/`actor_username`/`actor_kind` names match across events.py, world.py, and the agent guide.
4. **Backwards compat** — every event-shape change is additive (optional fields). The drawboard `width` field is loosened from `Literal` to `str` at the route boundary, but the validator still rejects bad values with the *same* error code — agents and the frontend both still get 422 with `error: "invalid_stroke"`.
