# Event Shape Unification + Error Envelope Standardization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the public event stream and error envelope of openParty *uniform* so agents and the frontend can consume them with a single code path. This plan is the **foundation spec (#01)** in the 2026-05-26 backlog round: every other spec assumes its changes have merged.

Concretely, three sweeps:

1. Flatten `join` events to the same shape as every other event (`actor_id`, `actor_username`, `actor_kind` at the top level plus spawn `x`/`y`/`zone`). **Hard cut — no `participant` alias preserved.** Rationale below.
2. Drop the `participant_id` field from `chat` events (and the matching `participant_id` field from `move`/`leave`). `actor_id` becomes the canonical key. Rationale: `actor_id` is the existing shared name; `participant_id` is the older legacy name that survives only on three event types. Spec #11 (agent onboarding) and the existing agent guide already steer agents toward `actor_*`.
3. Standardize the error envelope to `{"detail": {"error": "<code>", "message": "<human>", ...extra}}` across **every** route, including FastAPI's built-in 404s. Sweep `module_drawboard.py`, `module_notes.py`, `reactions.py`, `lighting.py`, `party_actions.py`, `parties.py`, `session.py`, `agents.py`, `dm.py`, `history.py`. Register a `StarletteHTTPException` handler in `main.py` so framework-generated 404/405 responses also use the envelope.

Also covered: documenting `seq` as a strict-monotonic global counter (with a regression test), and enumerating every event type in the agent guide with a one-line description + example payload.

**Architecture:** Pure backend type-shape change. Pydantic models in `app/events.py` get restructured; `app/world.py` builds them differently and `observe_since` no longer projects join into a nested `participant` dict. `app/errors.py` gains a single helper that always produces the wrapped envelope (`http_envelope`). `app/main.py` gains a `StarletteHTTPException` handler. Routes are rewritten to call the helper everywhere — no more string `detail=...`. Frontend `frontend/src/api/types.ts` is updated to match.

**Tech Stack:** FastAPI (Python 3.11), Pydantic v2, pytest + httpx. TypeScript types updated in lockstep on the frontend.

**Hard-cut rationale (no deprecation period):** openParty is pre-1.0. The only known consumers are (a) this repo's frontend, (b) the agent guide examples, (c) tests. All three are co-authored in this PR. Adding a deprecation alias would mean carrying two key names for every join event in the API surface — which is exactly the problem this spec exists to fix. We cut hard, update consumers, and call it out in the agent guide's "What changed" note.

**Coordination notes for other specs:**
- Other specs that emit new events (#05 gestures, #07 music, #11 welcome) must use the unified shape: top-level `actor_id`, `actor_username`, `actor_kind` — no nested `participant`.
- Other specs that introduce new errors must use `errors.http_envelope(status, code, message=...)` — not bare `HTTPException(detail="...")` strings.
- This plan does **NOT** add `actor_color` (spec #06 owns that).
- This plan does **NOT** add `actor_position_at_event` (spec #02 owns that).
- This plan does **NOT** add new event types — it only documents existing ones.

---

## Spec → Task Map

| Concern | Task |
|---|---|
| Flatten `join` event (hard cut) | Task 2, Task 3 |
| Drop `participant_id` from `chat`/`move`/`leave` (alias removal) | Task 4 |
| Promote `actor_id`/`actor_username`/`actor_kind` to required on move/chat/leave/reaction | Task 4 |
| Backfill `participant` snapshot fields in `/observe` initial snapshot (no regression) | Task 2 |
| Error envelope sweep — replace string `detail=...` | Task 5 |
| FastAPI built-in 404/405 wrapped in envelope | Task 6 |
| `seq` strict-monotonic global counter — document + test | Task 7 |
| Enumerate every event type in agent guide | Task 8 |
| Frontend type sync | Task 9 |
| Final verification / smoke | Task 10 |

---

## File Structure

**Backend — modify:**
- `backend/app/events.py` — restructure `JoinEvent`; promote actor fields to required on `MoveEvent`/`ChatEvent`/`LeaveEvent`/`ReactionEvent`; remove `participant_id` from those four.
- `backend/app/world.py` — build new join shape; update `observe_since` so it no longer wraps join into `participant: {...}`; update any internal code that reads `ev.participant_id`.
- `backend/app/errors.py` — add `http_envelope(status, code, message=..., **extras)` helper that returns an `HTTPException`. Add `PARTY_NOT_FOUND`, `NOT_FOUND`, `INVALID_LIMIT`, `INVALID_BEFORE_ID`, `SESSION_NOT_FOUND`, `AGENT_NOT_FOUND` codes.
- `backend/app/main.py` — register a `StarletteHTTPException` exception handler that lifts string-form details into the envelope shape.
- `backend/app/routes/party_actions.py` — use `http_envelope`; updated join return shape; flat join projection in observe-snapshot's `recent_chat` mapping where applicable.
- `backend/app/routes/parties.py` — use `http_envelope`.
- `backend/app/routes/session.py` — use `http_envelope`.
- `backend/app/routes/agents.py` — use `http_envelope`.
- `backend/app/routes/lighting.py` — use `http_envelope`.
- `backend/app/routes/module_notes.py` — use `http_envelope`.
- `backend/app/routes/module_drawboard.py` — use `http_envelope`.
- `backend/app/routes/reactions.py` — use `http_envelope`.
- `backend/app/routes/dm.py` — use `http_envelope` (string `detail="recipient_unknown"` etc. all promoted).
- `backend/app/routes/history.py` — use `http_envelope`.
- `backend/app/routes/principal.py` — use `http_envelope`.
- `backend/app/routes/agent_guide.py` — add event-type enumeration section and `seq` documentation; note the `join` flat shape and `actor_id`-only chat field.

**Backend — new tests:**
- `backend/tests/test_join_event_flat_shape.py`
- `backend/tests/test_chat_event_no_participant_id.py`
- `backend/tests/test_move_leave_actor_id_only.py`
- `backend/tests/test_error_envelope_shape.py`
- `backend/tests/test_error_envelope_builtin_404.py`
- `backend/tests/test_event_seq_monotonic.py`
- `backend/tests/test_agent_guide_event_catalog.py`

**Frontend — modify:**
- `frontend/src/api/types.ts` — update `JoinEvent`/`MoveEvent`/`ChatEvent`/`LeaveEvent` interfaces; promote `actor_*` fields to required; drop `participant_id` from `MoveEvent`/`ChatEvent`/`LeaveEvent`; restructure `JoinEvent` to flat actor fields. Add an `ApiError` interface.

Any frontend consumer that referenced `ev.participant_id` or `ev.participant.id` on the realtime stream must switch to `ev.actor_id`.

---

## Task 1: Pre-flight — confirm baseline tests pass

**Files:** none (read-only)

- [ ] **Step 1: Run backend test suite**

```bash
cd backend && python -m pytest -x --tb=short
```

Expected: ALL PASS. If anything fails on the current branch, STOP and report — do not absorb unrelated failures into this plan.

- [ ] **Step 2: Run frontend test suite**

```bash
cd frontend && npm test -- --run
```

Expected: ALL PASS.

- [ ] **Step 3: Snapshot current consumers**

Run two greps and save mentally — they tell you which files we will need to update in Tasks 2, 4, and 9.

```bash
cd backend && grep -rn "participant_id" app/ tests/
cd backend && grep -rn '"participant"' app/ tests/
cd frontend && grep -rn "participant_id\|JoinEvent\|participant:" src/ tests/
```

Expected: a finite list. No commit yet.

---

## Task 2: Flatten `JoinEvent` (model + world)

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/world.py`
- Test: `backend/tests/test_join_event_flat_shape.py`

**Decision:** `JoinEvent` carries `actor_id`/`actor_username`/`actor_kind`/`x`/`y`/`zone` at the top level. The legacy `participant: {...}` nesting is removed. The `/join` HTTP response on `party_actions.py` keeps its current nested `participant` body (it's a request/response shape, not an event) — only the event stream changes.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_join_event_flat_shape.py`:

```python
from tests.conftest import register_human, join_party


def test_join_event_is_flat(client):
    alice = register_human(client, username="Alice")
    cur_resp = client.get("/api/parties/cream-terrazzo/observe").json()
    cursor_before = cur_resp["cursor"]
    join_party(client, alice, "cream-terrazzo")
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor_before}"
    ).json()
    joins = [e for e in diff["events"] if e["type"] == "join"]
    assert len(joins) == 1
    j = joins[0]
    # Flat actor fields
    assert j["actor_id"] == alice["principal"]["id"]
    assert j["actor_username"] == "Alice"
    assert j["actor_kind"] == "human"
    # Spawn coordinates at top level
    assert "x" in j and "y" in j
    assert isinstance(j["x"], (int, float))
    assert isinstance(j["y"], (int, float))
    # Zone derived at event time (may be None if spawn lies in no zone)
    assert "zone" in j
    # No nested participant alias
    assert "participant" not in j
    # No legacy participant_id either
    assert "participant_id" not in j


def test_join_http_response_still_has_nested_participant(client):
    """The /join request/response body is distinct from the event stream.

    Frontend callers of POST /join read body.participant.x to place the
    avatar; that contract stays.
    """
    alice = register_human(client, username="Alice")
    resp = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": alice["principal"]},
    )
    body = resp.json()
    assert "participant" in body
    assert body["participant"]["username"] == "Alice"
```

- [ ] **Step 2: Run, confirm failure**

```bash
cd backend && python -m pytest tests/test_join_event_flat_shape.py -v
```

Expected: FAIL — current join event has `participant: {...}`, not flat fields.

- [ ] **Step 3: Restructure `JoinEvent` in `backend/app/events.py`**

Replace the existing `JoinEvent` class:

```python
class JoinEvent(BaseModel):
    seq: int
    type: Literal["join"] = "join"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    x: float
    y: float
    zone: str | None = None
    at: float
```

(Remove the `participant: Participant` field. Do **not** keep a `participant` alias.)

- [ ] **Step 4: Update `PartyWorld.join` in `backend/app/world.py`**

Replace the `join` method body:

```python
def join(self, participant: Participant) -> JoinEvent:
    self.participants[participant.id] = participant
    ev = JoinEvent(
        seq=self._next_seq(),
        actor_id=participant.id,
        actor_username=participant.username,
        actor_kind=participant.kind,
        x=participant.x,
        y=participant.y,
        zone=self.derive_zone(participant.x, participant.y),
        at=time.time(),
    )
    self._events.append(ev)
    self._emit(ev)
    self._recompute_all_drawboard_votes(time.time())
    return ev
```

- [ ] **Step 5: Update `observe_since` projection**

In `backend/app/world.py`, in `observe_since`, remove the special-case wrap for `JoinEvent`. Replace the existing `if isinstance(ev, JoinEvent): out.append({...})` branch with a plain `out.append(ev.model_dump())`:

```python
for ev in tail:
    if isinstance(ev, MoveEvent):
        latest_move_by_pid[ev.participant_id] = ev  # see Task 4: rename in same step
        continue
    if isinstance(ev, VoteChangedEvent):
        latest_vote_by_module[ev.module_id] = ev
        continue
    out.append(ev.model_dump())
```

(We leave the rest of `observe_since` alone for now — Task 4 will rename `participant_id` to `actor_id` in the move/leave/chat collapse.)

- [ ] **Step 6: Run the test, confirm pass**

```bash
cd backend && python -m pytest tests/test_join_event_flat_shape.py -v
```

Expected: PASS for `test_join_event_is_flat`. PASS for `test_join_http_response_still_has_nested_participant`.

- [ ] **Step 7: Run full backend suite — expect regressions in other test files**

```bash
cd backend && python -m pytest --tb=short
```

Some existing tests likely assert `ev["participant"]["id"]` on the join event. Update each such test to read `ev["actor_id"]`/`ev["actor_username"]`. Do not skip them — update them. Typical files: `test_observe_route.py`, `test_party_actions_route.py`, `test_event_actor_fields.py` (from the prior agent-experience plan).

Use this command to find them:

```bash
cd backend && grep -rn 'participant"\]' tests/ | grep -i join
cd backend && grep -rn 'participant.id\|participant\["id"\]' tests/
```

For each match in a *join-event* context, rewrite the assertion to `ev["actor_id"]` (and `actor_username` etc. as appropriate). Document each touched test file in the commit body.

- [ ] **Step 8: Re-run full suite**

```bash
cd backend && python -m pytest -x --tb=short
```

Expected: ALL PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/events.py backend/app/world.py \
        backend/tests/test_join_event_flat_shape.py \
        backend/tests/  # any updated test files
git commit -m "feat(events): flatten join event to actor_* + x/y/zone (hard cut)"
```

---

## Task 3: Update broadcast / WS frame helpers that referenced `JoinEvent.participant`

**Files:**
- Modify: `backend/app/realtime.py` (only if it references `JoinEvent.participant`)
- Modify: `backend/app/inbox.py`, `backend/app/inbox_ws.py` (same condition)

- [ ] **Step 1: Grep for references**

```bash
cd backend && grep -rn "JoinEvent\|\.participant\b" app/
```

For every match outside `events.py`/`world.py`/test files, decide whether the code reads the now-removed `.participant` attribute. Common spots: WS frame serialization in `realtime.py`, the broadcast hub used by `inbox_ws.py`. The `dm_store` / `dm.py` paths use a `Participant` *Pydantic model* in DM logic — those are unrelated and stay.

- [ ] **Step 2: Patch references**

For each call site that did `ev.participant.id` / `ev.participant.username` / etc., replace with `ev.actor_id` / `ev.actor_username` / `ev.actor_kind`. For positional access (`ev.participant.x`), use `ev.x`.

If a helper builds a "participant snapshot" dict from a join event for legacy WS frames, rebuild it from the live `self.participants[ev.actor_id]` lookup or from the flat fields directly:

```python
# before:
{"id": ev.participant.id, "kind": ev.participant.kind, ...}
# after:
{"id": ev.actor_id, "kind": ev.actor_kind, "username": ev.actor_username,
 "x": ev.x, "y": ev.y}
```

- [ ] **Step 3: Run full backend suite**

```bash
cd backend && python -m pytest -x --tb=short
```

Expected: ALL PASS. If anything fails, the failing assertion will show you which call site still expects the legacy nested shape.

- [ ] **Step 4: Commit**

```bash
git add backend/app/realtime.py backend/app/inbox*.py
git commit -m "refactor(events): switch internal consumers off JoinEvent.participant"
```

(Skip the commit if Step 1 found no consumers outside of files already touched in Task 2.)

---

## Task 4: Drop `participant_id`; promote `actor_*` to required on move/chat/leave/reaction

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/world.py`
- Test: `backend/tests/test_chat_event_no_participant_id.py`
- Test: `backend/tests/test_move_leave_actor_id_only.py`

**Decision:** `participant_id` is removed from `MoveEvent`, `ChatEvent`, `LeaveEvent`. `actor_id` is required (no longer Optional). `actor_username` and `actor_kind` are required. `ReactionEvent` already has `actor_id` required; promote `actor_username` and `actor_kind` to required for consistency.

This is a hard cut — no alias. The legacy alias was only ever optional documentation noise; the agent guide already steers agents to `actor_*`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_chat_event_no_participant_id.py`:

```python
from tests.conftest import register_human, join_party


def test_chat_event_uses_actor_id_only(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": alice["principal"], "text": "hello"},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    chats = [e for e in diff["events"] if e["type"] == "chat"]
    assert len(chats) == 1
    c = chats[0]
    assert c["actor_id"] == alice["principal"]["id"]
    assert c["actor_username"] == "Alice"
    assert c["actor_kind"] == "human"
    assert "participant_id" not in c
```

Create `backend/tests/test_move_leave_actor_id_only.py`:

```python
from tests.conftest import register_human, join_party


def test_move_event_uses_actor_id_only(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": alice["principal"], "x": 100.0, "y": 100.0},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    moves = [e for e in diff["events"] if e["type"] == "move"]
    assert moves, "expected one move event"
    m = moves[-1]
    assert m["actor_id"] == alice["principal"]["id"]
    assert m["actor_username"] == "Alice"
    assert m["actor_kind"] == "human"
    assert "participant_id" not in m


def test_leave_event_uses_actor_id_only(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": alice["principal"]},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    leaves = [e for e in diff["events"] if e["type"] == "leave"]
    assert len(leaves) == 1
    lv = leaves[0]
    assert lv["actor_id"] == alice["principal"]["id"]
    assert lv["actor_username"] == "Alice"
    assert lv["actor_kind"] == "human"
    assert "participant_id" not in lv


def test_reaction_event_actor_fields_required(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": alice["principal"], "emoji": "🔥"},
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    rxs = [e for e in diff["events"] if e["type"] == "reaction"]
    assert rxs and rxs[0]["actor_username"] == "Alice"
    assert rxs[0]["actor_kind"] == "human"
```

- [ ] **Step 2: Run, confirm failure**

```bash
cd backend && python -m pytest tests/test_chat_event_no_participant_id.py tests/test_move_leave_actor_id_only.py -v
```

Expected: FAIL — `participant_id` is still present on every event.

- [ ] **Step 3: Update event models in `backend/app/events.py`**

Replace the four event classes:

```python
class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"] = "leave"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    at: float


class MoveEvent(BaseModel):
    seq: int
    type: Literal["move"] = "move"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    x: float
    y: float
    at: float


class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    text: str
    at: float


class ReactionEvent(BaseModel):
    seq: int
    type: Literal["reaction"] = "reaction"
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    emoji: str
    expires_at: float
    at: float
```

- [ ] **Step 4: Update `PartyWorld` constructors in `backend/app/world.py`**

In each event-builder method, drop `participant_id=...` and rely on `**self._actor_fields(participant_id)`. Concretely:

```python
def leave(self, participant_id: str) -> LeaveEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    actor = self._actor_fields(participant_id)
    del self.participants[participant_id]
    ev = LeaveEvent(seq=self._next_seq(), at=time.time(), **actor)
    self._events.append(ev)
    self._emit(ev)
    self._recompute_all_drawboard_votes(time.time())
    return ev


def move(self, participant_id: str, x: float, y: float) -> MoveEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    current = self.participants[participant_id]
    new_x, new_y = slide(
        (current.x, current.y),
        (float(x), float(y)),
        self._wall_rects,
        self._party.worldSize,
    )
    self.participants[participant_id] = current.model_copy(
        update={"x": new_x, "y": new_y}
    )
    ev = MoveEvent(
        seq=self._next_seq(),
        x=new_x,
        y=new_y,
        at=time.time(),
        **self._actor_fields(participant_id),
    )
    self._events.append(ev)
    self._emit(ev)
    self._recompute_all_drawboard_votes(time.time())
    return ev


def chat(self, participant_id: str, text: str) -> ChatEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    cleaned = validate_chat_text(text)
    at = time.time()
    sender = self.participants[participant_id]
    if self._db is not None:
        db_module.insert_broadcast(
            self._db,
            party_slug=self._party_slug,
            sender_kind=sender.kind,
            sender_id=sender.id,
            sender_name=sender.username,
            text=cleaned,
            at=at,
        )
    ev = ChatEvent(
        seq=self._next_seq(),
        text=cleaned,
        at=time.time(),
        **self._actor_fields(participant_id),
    )
    self._events.append(ev)
    self._emit(ev)
    return ev


def react(self, participant_id: str, emoji: str) -> ReactionEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    cleaned = validate_reaction_emoji(emoji)
    now = time.time()
    expires_at = now + REACTION_LIFETIME_SECONDS
    self.active_reactions[participant_id] = Reaction(
        actor_id=participant_id, emoji=cleaned, expires_at=expires_at,
    )
    ev = ReactionEvent(
        seq=self._next_seq(),
        emoji=cleaned,
        expires_at=expires_at,
        at=now,
        **self._actor_fields(participant_id),
    )
    self._events.append(ev)
    self._emit(ev)
    return ev
```

- [ ] **Step 5: Update `observe_since` — keep coalescing by actor**

In `backend/app/world.py`, the move-coalescing dict now keys on `actor_id`:

```python
def observe_since(self, since: int) -> dict:
    if since < 0:
        since = 0
    tail = self._events[since:]
    latest_move_by_actor: dict[str, MoveEvent] = {}
    latest_vote_by_module: dict[str, VoteChangedEvent] = {}
    out: list[dict] = []
    for ev in tail:
        if isinstance(ev, MoveEvent):
            latest_move_by_actor[ev.actor_id] = ev
            continue
        if isinstance(ev, VoteChangedEvent):
            latest_vote_by_module[ev.module_id] = ev
            continue
        out.append(ev.model_dump())
    for mv in latest_move_by_actor.values():
        d = mv.model_dump()
        d["zone"] = self.derive_zone(mv.x, mv.y)
        out.append(d)
    for v in latest_vote_by_module.values():
        out.append(v.model_dump())
    out.sort(key=lambda e: e["seq"])
    return {"events": out, "cursor": self.cursor}
```

- [ ] **Step 6: Sweep remaining `participant_id` references**

```bash
cd backend && grep -rn "participant_id" app/ tests/
```

For every match in `app/` (outside `world.py`'s function *parameter* names, which can stay — they are internal): rename to `actor_id` if it reads the event field.

In particular check `app/realtime.py` and any WS frame builder — those often did `ev.participant_id` to attribute a chat bubble. Replace with `ev.actor_id`.

For every match in `tests/`: if the assertion is on an event-dict key, rewrite to `actor_id`. Inline the update in this commit.

- [ ] **Step 7: Run the two new tests, confirm pass**

```bash
cd backend && python -m pytest tests/test_chat_event_no_participant_id.py tests/test_move_leave_actor_id_only.py -v
```

Expected: PASS.

- [ ] **Step 8: Run full backend suite**

```bash
cd backend && python -m pytest -x --tb=short
```

Expected: ALL PASS. Fix any remaining test fallout in place — they will mostly be old tests asserting `ev["participant_id"]`.

- [ ] **Step 9: Commit**

```bash
git add backend/app/events.py backend/app/world.py backend/app/realtime.py \
        backend/tests/test_chat_event_no_participant_id.py \
        backend/tests/test_move_leave_actor_id_only.py \
        backend/tests/
git commit -m "feat(events): drop participant_id, require actor_* on move/chat/leave/reaction"
```

---

## Task 5: Error envelope — sweep string-form `HTTPException` calls

**Files:**
- Modify: `backend/app/errors.py` (add helper + codes)
- Modify: every route file with a string `detail=...`
- Test: `backend/tests/test_error_envelope_shape.py`

**Decision:** Every API error response body is `{"detail": {"error": "<code>", "message": "<human>", ...extra}}`. The `message` is always present (a human-readable English sentence). Extras (like `allowed_colors`, `retry_after_ms`, `interactionRect`) are optional and additive.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_error_envelope_shape.py`:

```python
"""Every API error body MUST look like:

    {"detail": {"error": "<snake_case_code>", "message": "<sentence>",
                ...optional extras}}

This test stitches together one example per error code in the codebase
and asserts the contract.
"""
from tests.conftest import register_human


def _assert_envelope(body, expected_code):
    assert isinstance(body, dict), body
    detail = body.get("detail")
    assert isinstance(detail, dict), f"detail not a dict: {detail!r}"
    assert detail.get("error") == expected_code, detail
    assert isinstance(detail.get("message"), str) and detail["message"], detail


def test_principal_unknown_is_envelope(client):
    resp = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": "does-not-exist"}},
    )
    assert resp.status_code == 401
    _assert_envelope(resp.json(), "principal_unknown")


def test_not_in_party_chat_is_envelope(client):
    sess = register_human(client, username="Alice")
    # No join — chat should be 409 not_in_party
    resp = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": sess["principal"], "text": "hi"},
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), "not_in_party")


def test_party_not_found_is_envelope(client):
    sess = register_human(client, username="Alice")
    resp = client.post(
        "/api/parties/no-such-party/join",
        json={"principal": sess["principal"]},
    )
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "party_not_found")


def test_self_dm_is_envelope(client):
    sess = register_human(client, username="Alice")
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": sess["principal"],
            "recipient": {
                "kind": sess["principal"]["kind"],
                "id": sess["principal"]["id"],
            },
            "text": "to self",
        },
    )
    # Whatever the status is, the body must be the envelope shape.
    assert resp.status_code >= 400
    _assert_envelope(resp.json(), "self_dm")


def test_recipient_unknown_is_envelope(client):
    sess = register_human(client, username="Alice")
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": sess["principal"],
            "recipient": {"kind": "human", "id": "no-such-recipient"},
            "text": "hi",
        },
    )
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "recipient_unknown")


def test_session_not_found_is_envelope(client):
    resp = client.get("/api/session/no-such-session")
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "session_not_found")
```

- [ ] **Step 2: Run, confirm failure**

```bash
cd backend && python -m pytest tests/test_error_envelope_shape.py -v
```

Expected: every assertion that hits a current string-detail route FAILS.

- [ ] **Step 3: Extend `backend/app/errors.py`**

Replace the file body with:

```python
"""Canonical error codes returned to API clients.

Every error response uses the envelope shape:

    {"detail": {"error": "<code>", "message": "<human>", ...extras}}

Use `http_envelope` to build the FastAPI HTTPException — never construct
HTTPException with a string `detail` directly.
"""
from fastapi import HTTPException


# Codes — one constant per error.
PRINCIPAL_UNKNOWN = "principal_unknown"
NOT_IN_PARTY = "not_in_party"
INVALID_COLOR = "invalid_color"
INVALID_CHAT_TEXT = "invalid_chat_text"
VALIDATION_ERROR = "validation_error"
SELF_DM = "self_dm"
RECIPIENT_UNKNOWN = "recipient_unknown"
DM_FORBIDDEN = "dm_forbidden"
PARTY_NOT_FOUND = "party_not_found"
SESSION_NOT_FOUND = "session_not_found"
AGENT_NOT_FOUND = "agent_not_found"
INVALID_LIMIT = "invalid_limit"
INVALID_BEFORE_ID = "invalid_before_id"
NOT_FOUND = "not_found"  # generic fall-back


# Default human-readable messages keyed by code. Routes may override.
_DEFAULT_MESSAGES: dict[str, str] = {
    PRINCIPAL_UNKNOWN: "The provided principal could not be resolved.",
    NOT_IN_PARTY: "You must join the party before performing this action.",
    INVALID_COLOR: "The provided color is not in the allow-list.",
    INVALID_CHAT_TEXT: "Chat text failed validation.",
    VALIDATION_ERROR: "Request body failed validation.",
    SELF_DM: "You cannot send a direct message to yourself.",
    RECIPIENT_UNKNOWN: "The DM recipient could not be resolved.",
    DM_FORBIDDEN: "You are not a participant in this thread.",
    PARTY_NOT_FOUND: "No party exists with that slug.",
    SESSION_NOT_FOUND: "No session exists with that id.",
    AGENT_NOT_FOUND: "No agent exists with that id.",
    INVALID_LIMIT: "The `limit` query parameter is out of range.",
    INVALID_BEFORE_ID: "The `before_id` query parameter is invalid.",
    NOT_FOUND: "The requested resource was not found.",
}


def envelope(error: str, *, message: str | None = None, **extras: object) -> dict[str, object]:
    """Build a structured detail body: ``{"error": code, "message": ..., ...extras}``.

    `message` falls back to a sensible default when omitted.
    """
    msg = message if message is not None else _DEFAULT_MESSAGES.get(error, error)
    return {"error": error, "message": msg, **extras}


def http_envelope(
    status_code: int,
    error: str,
    *,
    message: str | None = None,
    **extras: object,
) -> HTTPException:
    """Build a FastAPI ``HTTPException`` whose ``detail`` is the standard envelope."""
    return HTTPException(
        status_code=status_code,
        detail=envelope(error, message=message, **extras),
    )
```

- [ ] **Step 4: Sweep every route file**

For each route file, replace string-form raises with `http_envelope`. Below is the complete list of changes. Apply them in one commit so we don't ship a half-converted API.

**`backend/app/routes/party_actions.py`** — top of file:
```python
from app.errors import (
    INVALID_CHAT_TEXT,
    NOT_IN_PARTY,
    PARTY_NOT_FOUND,
    envelope,
    http_envelope,
)
```
Replace bodies:
```python
def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    return world
```
Each `raise HTTPException(status_code=409, detail=NOT_IN_PARTY)` becomes
`raise http_envelope(409, NOT_IN_PARTY)`. The chat-validation block:
```python
    except ChatValidationError as exc:
        raise http_envelope(422, INVALID_CHAT_TEXT, message=str(exc))
```

**`backend/app/routes/reactions.py`** — same pattern. `_world` uses
`raise http_envelope(404, PARTY_NOT_FOUND)`. The reaction-validation block keeps the
existing `allowed_emojis` extra but routed through `http_envelope`:
```python
from app.errors import NOT_IN_PARTY, PARTY_NOT_FOUND, http_envelope
# ...
    except ReactionValidationError as exc:
        raise http_envelope(
            422,
            "invalid_emoji",
            message=str(exc),
            allowed_emojis=list(REACTION_EMOJI_ALLOWLIST),
        )
```

**`backend/app/routes/lighting.py`**:
```python
from app.errors import NOT_IN_PARTY, PARTY_NOT_FOUND, http_envelope
# ...
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
# ...
    except ParticipantNotInPartyError:
        raise http_envelope(409, NOT_IN_PARTY)
    except ValueError as exc:
        raise http_envelope(422, "invalid_preset", message=str(exc))
```

**`backend/app/routes/module_notes.py`** — replace `_world` and `_map_world_errors`:
```python
from app.errors import NOT_IN_PARTY, PARTY_NOT_FOUND, http_envelope

def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise http_envelope(404, PARTY_NOT_FOUND)
    return world


def _map_world_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, ParticipantNotInPartyError):
        return http_envelope(409, NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        return http_envelope(409, "not_in_range",
                             message="You are not within the module's interaction zone.")
    if isinstance(exc, PartyWorld.LimitReachedError):
        return http_envelope(409, "limit_reached",
                             message="You have reached the per-user note limit.")
    if isinstance(exc, PartyWorld.NotAuthorError):
        return http_envelope(403, "not_author",
                             message="Only the note's author can modify it.")
    if isinstance(exc, KeyError):
        return http_envelope(404, "not_found")
    if isinstance(exc, NoteValidationError):
        return http_envelope(
            422,
            "invalid_note",
            message=str(exc),
            allowed_colors=list(STICKY_COLOR_ALLOWLIST),
        )
    return http_envelope(422, "invalid_note", message=str(exc))
```

**`backend/app/routes/module_drawboard.py`** — analogous. Replace each
`HTTPException(status_code=..., detail=...)` with `http_envelope(...)`.

**`backend/app/routes/dm.py`** — every string `detail=` becomes a code via
`http_envelope`:
```python
from app.errors import (
    DM_FORBIDDEN,
    INVALID_CHAT_TEXT,
    PRINCIPAL_UNKNOWN,
    RECIPIENT_UNKNOWN,
    http_envelope,
)
# ...
    except ValidationError:
        raise http_envelope(404, RECIPIENT_UNKNOWN)
# ...
    except ChatValidationError as exc:
        raise http_envelope(422, INVALID_CHAT_TEXT, message=str(exc))
    except DmError as exc:
        raise http_envelope(exc.status, exc.code)
# threads:
    except ValidationError:
        raise http_envelope(401, PRINCIPAL_UNKNOWN)
# history:
    except ValidationError:
        raise http_envelope(401, PRINCIPAL_UNKNOWN)
    # ...
    if len(parts) != 2 or key not in parts:
        raise http_envelope(403, DM_FORBIDDEN)
```

Note: the existing `DmError.code` values (e.g. `"self_dm"`) already match
the new code names — no translation table needed.

**`backend/app/routes/session.py`** — both 404 raises become
`raise http_envelope(404, SESSION_NOT_FOUND)`.

**`backend/app/routes/agents.py`** — both `"agent not found"` raises become
`raise http_envelope(404, AGENT_NOT_FOUND)`. The other `HTTPException` that
guards validation in this file (line 33) — convert similarly using its
existing code.

**`backend/app/routes/parties.py`** — `"party not found"` ⇒
`http_envelope(404, PARTY_NOT_FOUND)`.

**`backend/app/routes/history.py`** — `"party not found"` ⇒
`http_envelope(404, PARTY_NOT_FOUND)`; `"invalid limit"` ⇒
`http_envelope(400, INVALID_LIMIT)`; `"invalid before_id"` ⇒
`http_envelope(400, INVALID_BEFORE_ID)`.

**`backend/app/routes/principal.py`** — `HTTPException(status_code=401, detail=PRINCIPAL_UNKNOWN)` becomes `http_envelope(401, PRINCIPAL_UNKNOWN)`. (PRINCIPAL_UNKNOWN was already a code string; previously the body was `{"detail": "principal_unknown"}` — a string. Now it's the envelope dict.)

- [ ] **Step 5: Run new test, confirm pass**

```bash
cd backend && python -m pytest tests/test_error_envelope_shape.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full backend suite — fix regressions in old tests**

```bash
cd backend && python -m pytest --tb=short
```

Many old tests assert `resp.json()["detail"] == "principal_unknown"` (string). Update them to `resp.json()["detail"]["error"] == "principal_unknown"`. Search:

```bash
cd backend && grep -rn '\["detail"\] ==' tests/
cd backend && grep -rn "detail.*==.*'" tests/
```

Update each match. Do NOT loosen the assertions — the new shape is the contract.

- [ ] **Step 7: Final suite pass**

```bash
cd backend && python -m pytest -x --tb=short
```

Expected: ALL PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/errors.py backend/app/routes/ backend/tests/test_error_envelope_shape.py backend/tests/
git commit -m "feat(errors): standardize envelope to {detail:{error,message,...}} across routes"
```

---

## Task 6: FastAPI built-in 404/405 wrapped in envelope

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_error_envelope_builtin_404.py`

FastAPI's default 404 (route-not-found) and 405 (method-not-allowed) return `{"detail": "Not Found"}` — a string. Register a handler so they emit the envelope shape too. Use Starlette's `HTTPException` so the handler covers both framework-generated and user-raised string-form details (defense in depth).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_error_envelope_builtin_404.py`:

```python
def _assert_envelope(body, expected_code):
    detail = body.get("detail")
    assert isinstance(detail, dict), detail
    assert detail.get("error") == expected_code, detail
    assert isinstance(detail.get("message"), str), detail


def test_unknown_route_returns_envelope(client):
    resp = client.get("/api/no-such-endpoint")
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "not_found")


def test_wrong_method_returns_envelope(client):
    # /api/health is GET-only
    resp = client.post("/api/health")
    assert resp.status_code == 405
    _assert_envelope(resp.json(), "method_not_allowed")
```

- [ ] **Step 2: Run, confirm failure**

```bash
cd backend && python -m pytest tests/test_error_envelope_builtin_404.py -v
```

Expected: FAIL — body is `{"detail": "Not Found"}`.

- [ ] **Step 3: Register the handler in `backend/app/main.py`**

After the existing `RequestValidationError` handler, add:

```python
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Wrap any HTTPException whose detail is still a bare string into
    the standard envelope. HTTPExceptions raised via ``http_envelope``
    already carry a dict detail; we pass those through untouched.
    """
    detail = exc.detail
    if isinstance(detail, dict) and "error" in detail:
        # Already enveloped.
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    # Map known framework messages onto stable codes.
    code_map = {
        404: ("not_found", "The requested resource was not found."),
        405: ("method_not_allowed", "HTTP method not allowed for this route."),
        401: ("unauthorized", "Authentication required."),
        403: ("forbidden", "Access denied."),
    }
    code, default_msg = code_map.get(exc.status_code, ("http_error", str(detail) or "HTTP error."))
    message = default_msg if not isinstance(detail, str) or detail.lower() in ("not found", "method not allowed") else detail
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": envelope(code, message=message)},
    )
```

Import the necessary symbols at the top of `main.py`:

```python
from app.errors import NOT_FOUND, VALIDATION_ERROR, envelope
```

(`NOT_FOUND` already exists in `errors.py` per Task 5.)

- [ ] **Step 4: Run the new test, confirm pass**

```bash
cd backend && python -m pytest tests/test_error_envelope_builtin_404.py -v
```

Expected: PASS.

- [ ] **Step 5: Full suite**

```bash
cd backend && python -m pytest -x --tb=short
```

Expected: ALL PASS. If any test previously relied on `{"detail": "Not Found"}` exactly, update it to the envelope shape.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/tests/test_error_envelope_builtin_404.py
git commit -m "feat(errors): wrap framework HTTPExceptions in standard envelope"
```

---

## Task 7: Document `seq` as a monotonic global counter (test + guide)

**Files:**
- Test: `backend/tests/test_event_seq_monotonic.py`
- Modify: `backend/app/routes/agent_guide.py` (add a `seq` paragraph — full content lives in Task 8)

`seq` is already implemented as a monotonic global counter (`self._next_seq()` returns `len(self._events) + 1`). The task here is **(a)** lock the contract with a regression test that drives several event types and asserts strict monotonicity, **(b)** make sure agents know what to expect.

- [ ] **Step 1: Write the failing test (test docs the contract, not its absence)**

Create `backend/tests/test_event_seq_monotonic.py`:

```python
"""`seq` is a monotonic, strictly-increasing counter spanning ALL event
types in a single party world. Agents rely on this to order events
without per-type bookkeeping.
"""
from tests.conftest import register_human, join_party


def test_seq_strictly_monotonic_across_types(client):
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")

    # Drive a mix of event types.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": alice["principal"], "x": 200.0, "y": 200.0},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": alice["principal"], "text": "hello world"},
    )
    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": bob["principal"], "emoji": "🔥"},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": bob["principal"], "x": 250.0, "y": 250.0},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": bob["principal"], "text": "hi alice"},
    )
    client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": alice["principal"]},
    )

    diff = client.get("/api/parties/cream-terrazzo/observe?since=0").json()
    events = diff["events"]
    assert len(events) >= 6
    seqs = [e["seq"] for e in events]
    # Strictly monotonic.
    assert seqs == sorted(seqs), f"events not sorted by seq: {seqs}"
    assert len(set(seqs)) == len(seqs), f"duplicate seqs: {seqs}"
    # Per-type subsequences are also monotonic (each subset preserves global order).
    for t in {"move", "chat", "reaction", "join", "leave"}:
        sub = [e["seq"] for e in events if e["type"] == t]
        assert sub == sorted(sub), f"non-monotonic within {t}: {sub}"
    # Cursor equals max seq.
    assert diff["cursor"] == max(seqs)
```

- [ ] **Step 2: Run, confirm pass**

```bash
cd backend && python -m pytest tests/test_event_seq_monotonic.py -v
```

Expected: PASS immediately (the contract already holds). If it FAILS, fix `_next_seq` to be a single shared counter — it should be, but verify.

- [ ] **Step 3: Commit just the test (the guide update lands in Task 8)**

```bash
git add backend/tests/test_event_seq_monotonic.py
git commit -m "test(events): lock seq as strictly-monotonic global counter"
```

---

## Task 8: Agent guide — event catalog, `seq` doc, new shapes

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Test: `backend/tests/test_agent_guide_event_catalog.py`

Add three sections to the guide: `## Events`, `## seq ordering`, and an updated `## What changed` block summarizing the hard cuts so existing agents notice. Enumerate every event type defined in `events.py` with a one-line description and an example payload.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agent_guide_event_catalog.py`:

```python
EXPECTED_EVENT_TYPES = (
    "join",
    "leave",
    "move",
    "chat",
    "reaction",
    "lighting_changed",
    "note_created",
    "note_updated",
    "note_deleted",
    "stroke_added",
    "stroke_dropped",
    "board_cleared",
    "vote_changed",
)


def test_agent_guide_enumerates_every_event_type(client):
    body = client.get("/api/agent-guide").text
    for t in EXPECTED_EVENT_TYPES:
        assert f"`{t}`" in body, f"event type {t} not documented in agent guide"


def test_agent_guide_documents_seq_as_monotonic_global(client):
    body = client.get("/api/agent-guide").text
    assert "monotonic" in body.lower()
    assert "seq" in body
    assert "global" in body.lower()


def test_agent_guide_uses_flat_join_shape(client):
    body = client.get("/api/agent-guide").text
    # Old nested shape must not appear as a recommendation.
    assert '"participant": {' not in body
    # New flat fields must be referenced.
    assert "actor_id" in body
    assert "actor_username" in body
    assert "actor_kind" in body


def test_agent_guide_calls_out_participant_id_removal(client):
    body = client.get("/api/agent-guide").text
    assert "participant_id" in body  # mentioned in "what changed" so agents notice
    assert "actor_id" in body
```

- [ ] **Step 2: Run, confirm failure**

```bash
cd backend && python -m pytest tests/test_agent_guide_event_catalog.py -v
```

Expected: FAIL.

- [ ] **Step 3: Update `backend/app/routes/agent_guide.py`**

Add the following sections to `_GUIDE` (place after the existing Events / Modules sections — adapt section numbering to the current file structure):

```markdown
## Events: the full catalog

Every event in `/observe` carries a `seq` (see next section) and a `type`.
Actor fields (`actor_id`, `actor_username`, `actor_kind`) appear on every
event whose source is a participant — use `actor_id` as the single
identity key across all event types.

| `type` | Description | Example payload |
|---|---|---|
| `join` | A participant joined the party. Spawn coords at top level. | `{"type":"join","seq":12,"actor_id":"h_alice","actor_username":"Alice","actor_kind":"human","x":640,"y":360,"zone":"center","at":1716700000.0}` |
| `leave` | A participant left or was disconnected. | `{"type":"leave","seq":34,"actor_id":"h_alice","actor_username":"Alice","actor_kind":"human","at":1716700050.0}` |
| `move` | A participant's position changed (post-collision). | `{"type":"move","seq":40,"actor_id":"h_alice","actor_username":"Alice","actor_kind":"human","x":700,"y":360,"at":1716700060.0}` |
| `chat` | A participant sent a chat message. | `{"type":"chat","seq":42,"actor_id":"h_alice","actor_username":"Alice","actor_kind":"human","text":"hi","at":1716700061.0}` |
| `reaction` | A floating emoji reaction (1s TTL). | `{"type":"reaction","seq":43,"actor_id":"h_alice","actor_username":"Alice","actor_kind":"human","emoji":"🔥","expires_at":1716700062.0,"at":1716700061.0}` |
| `lighting_changed` | Room lighting preset changed. | `{"type":"lighting_changed","seq":44,"preset":"dusk","changed_by":"h_alice","at":1716700070.0}` |
| `note_created` | A sticky note was created on a stickynotes module. | `{"type":"note_created","seq":45,"module_id":"sticky-1","note":{"id":"...","text":"hi","color":"yellow",...},"at":...}` |
| `note_updated` | An existing sticky note's text/color/position changed. | `{"type":"note_updated","seq":46,"module_id":"sticky-1","note":{...},"at":...}` |
| `note_deleted` | A sticky note was deleted by its author. | `{"type":"note_deleted","seq":47,"module_id":"sticky-1","note_id":"...","at":...}` |
| `stroke_added` | A new stroke was drawn on a drawboard. | `{"type":"stroke_added","seq":48,"module_id":"draw-1","stroke":{"id":"...","points":[...],"color":"#ffd54f","width":"med"},"at":...}` |
| `stroke_dropped` | An older stroke was evicted (board cap reached). | `{"type":"stroke_dropped","seq":49,"module_id":"draw-1","stroke_id":"...","at":...}` |
| `board_cleared` | The drawboard was cleared by a passing vote. | `{"type":"board_cleared","seq":50,"module_id":"draw-1","cleared_by":"h_alice","at":...}` |
| `vote_changed` | The clear-board vote tally changed (or in-zone population changed). | `{"type":"vote_changed","seq":51,"module_id":"draw-1","votes":2,"needed":3,"at":...}` |

## seq ordering

`seq` is a strictly-monotonic, **global** counter scoped to a party world.
It is shared across all event types — so `move`, `chat`, `reaction`,
`vote_changed`, and `note_created` all draw from the same incrementing
sequence. Agents should:

- Sort events by `seq` ascending — never assume `events[]` arrives sorted.
- Use the maximum observed `seq` (or `cursor` from the response, which
  equals it) as the next `?since=` value.
- Never rely on `seq` being contiguous *within* a single type — gaps are
  expected because other event types are interleaved.

## What changed (2026-05-26)

- `join` events are now flat: `actor_id`, `actor_username`, `actor_kind`,
  `x`, `y`, `zone` at the top level. The previous nested
  `participant: {...}` shape has been removed (no deprecation period —
  openParty is pre-1.0). The `/join` HTTP response body still contains a
  nested `participant` object — that's a request/response contract,
  separate from the event stream.
- `move`, `chat`, and `leave` events no longer carry `participant_id`.
  Use `actor_id` everywhere.
- Every error response is now the envelope shape
  `{"detail": {"error": "<code>", "message": "<human>", ...extras}}` —
  including FastAPI's built-in 404/405. Match on `detail.error`.
```

Then add a "Common error codes" subsection so agents can pattern-match:

```markdown
### Common error codes

| HTTP | `error` | Meaning |
|---|---|---|
| 401 | `principal_unknown` | The `principal` you sent is not registered. Re-register. |
| 404 | `party_not_found` | No party at this slug. |
| 404 | `session_not_found` | The session id is invalid. |
| 404 | `agent_not_found` | The agent id is invalid. |
| 404 | `not_found` | Generic — the requested resource is gone. |
| 405 | `method_not_allowed` | Wrong HTTP verb for the route. |
| 409 | `not_in_party` | You must `/join` before this action. |
| 409 | `not_in_range` | Walk into the module's `interactionRect` first. |
| 409 | `limit_reached` | You hit a per-user cap (e.g. notes). |
| 403 | `not_author` | Only the author can mutate this resource. |
| 403 | `dm_forbidden` | You are not a participant in this DM thread. |
| 422 | `invalid_chat_text` | See `message` for which rule failed. |
| 422 | `invalid_emoji` | Body includes `allowed_emojis`. |
| 422 | `invalid_note` | Body includes `allowed_colors`. |
| 422 | `invalid_stroke` | Body includes `allowed_colors`/`allowed_widths`. |
| 422 | `validation_error` | Request body failed Pydantic validation. Body includes `fields[]`. |
```

- [ ] **Step 4: Run the new test, confirm pass**

```bash
cd backend && python -m pytest tests/test_agent_guide_event_catalog.py -v
```

Expected: PASS.

- [ ] **Step 5: Full backend suite**

```bash
cd backend && python -m pytest -x --tb=short
```

Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_event_catalog.py
git commit -m "docs(agent-guide): event catalog, seq ordering, error code table"
```

---

## Task 9: Frontend type sync

**Files:**
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Inspect current event types**

```bash
cd frontend && grep -n "JoinEvent\|ChatEvent\|MoveEvent\|LeaveEvent\|ReactionEvent\|participant_id" src/api/types.ts
```

- [ ] **Step 2: Rewrite event types**

Replace the relevant interfaces in `frontend/src/api/types.ts`:

```ts
export type ActorKind = 'human' | 'agent';

export interface ActorRef {
  actor_id: string;
  actor_username: string;
  actor_kind: ActorKind;
}

export interface JoinEvent extends ActorRef {
  type: 'join';
  seq: number;
  x: number;
  y: number;
  zone: string | null;
  at: number;
}

export interface LeaveEvent extends ActorRef {
  type: 'leave';
  seq: number;
  at: number;
}

export interface MoveEvent extends ActorRef {
  type: 'move';
  seq: number;
  x: number;
  y: number;
  zone?: string | null;
  at: number;
}

export interface ChatEvent extends ActorRef {
  type: 'chat';
  seq: number;
  text: string;
  at: number;
}

export interface ReactionEvent extends ActorRef {
  type: 'reaction';
  seq: number;
  emoji: string;
  expires_at: number;
  at: number;
}

export interface ApiError {
  error: string;
  message: string;
  // Optional context — varies by error code.
  allowed_colors?: string[];
  allowed_widths?: string[];
  allowed_emojis?: string[];
  fields?: Array<{ field: string | null; message: string }>;
  // Any extra context provided by the server.
  [key: string]: unknown;
}

export interface ApiErrorResponse {
  detail: ApiError;
}
```

(Leave the non-realtime types — `Participant`, `Room`, `Zone`, etc. — untouched. Those describe HTTP request/response bodies, not events.)

- [ ] **Step 3: Patch consumers of removed fields**

```bash
cd frontend && grep -rn "participant_id\|ev\.participant\b" src/ tests/
```

For each match in source files, rewrite to `actor_id` (or `actor_username` / etc.). Common spots: chat bubble rendering, avatar lookup keyed by `event.participant_id`, join handlers reading `event.participant.id`.

For the join handler specifically (likely in `useRealtimeParty.ts` or a similar hook), the avatar spawn rendering changes from:

```ts
case 'join':
  addParticipant(event.participant); // OLD
```

to:

```ts
case 'join':
  addParticipant({
    id: event.actor_id,
    username: event.actor_username,
    kind: event.actor_kind,
    x: event.x,
    y: event.y,
    // color is filled by spec #06; for now, look it up from the snapshot
    // by id, or use a placeholder.
  });
```

Note: the snapshot still carries full `Participant` objects (with `color`) for everyone in the room — that pathway hasn't changed. The join event reduces to "minimum-to-render-an-arrival"; consumers that need `color` can either look it up in the existing participants map (which the same `observe` call populates) or wait for spec #06's `actor_color` field.

- [ ] **Step 4: Run frontend tests**

```bash
cd frontend && npm test -- --run
```

Expected: ALL PASS. If a test mocks an event with `participant_id`, update the mock to use `actor_id`.

- [ ] **Step 5: Run typecheck**

```bash
cd frontend && npm run typecheck 2>/dev/null || npx tsc --noEmit
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/ frontend/tests/
git commit -m "feat(frontend): consume flat join + actor_id-only event shape"
```

---

## Task 10: Final verification + smoke test

**Files:** none (verification only — no source changes)

- [ ] **Step 1: Full backend suite**

```bash
cd backend && python -m pytest --tb=short
```

Expected: ALL PASS.

- [ ] **Step 2: Full frontend suite + typecheck**

```bash
cd frontend && npm test -- --run && npx tsc --noEmit
```

Expected: ALL PASS / clean.

- [ ] **Step 3: Manual smoke — run the API and curl the contract**

```bash
cd backend && python -m uvicorn app.main:app --port 8901 &
sleep 1

# Built-in 404 is enveloped:
curl -s http://localhost:8901/api/no-such-route | python -m json.tool

# Wrong method is enveloped:
curl -s -X POST http://localhost:8901/api/health | python -m json.tool

# Party 404 is enveloped:
curl -s -X POST http://localhost:8901/api/parties/no-such/join \
     -H 'content-type: application/json' \
     -d '{"principal":{"kind":"human","id":"x"}}' | python -m json.tool

# Agent guide mentions every event type:
curl -s http://localhost:8901/api/agent-guide | grep -E "(`join`|`leave`|`move`|`chat`|`reaction`|`note_created`|`stroke_added`|`vote_changed`)"

kill %1
```

Expected: every response body is `{"detail": {"error": "...", "message": "..."}}`. The agent-guide grep matches all listed event types.

- [ ] **Step 4: Confirm commit log is clean**

```bash
git log --oneline main..HEAD
```

Expected: a series of small, well-titled commits — one per task (or split into two where the task touched many files):

```
feat(events): flatten join event to actor_* + x/y/zone (hard cut)
refactor(events): switch internal consumers off JoinEvent.participant   # (only if non-empty)
feat(events): drop participant_id, require actor_* on move/chat/leave/reaction
feat(errors): standardize envelope to {detail:{error,message,...}} across routes
feat(errors): wrap framework HTTPExceptions in standard envelope
test(events): lock seq as strictly-monotonic global counter
docs(agent-guide): event catalog, seq ordering, error code table
feat(frontend): consume flat join + actor_id-only event shape
```

No fixup commits, no "wip".

---

## Self-review checklist

1. **Hard cut is real.** `participant: {...}` is gone from join events. `participant_id` is gone from move/chat/leave events. There is no alias. The agent guide's "What changed" section explains why.
2. **Every route emits the envelope.** `grep -rn 'HTTPException(status_code=.*detail="' backend/app/routes/` returns zero matches. `grep -rn 'detail=PRINCIPAL_UNKNOWN' backend/app/routes/` returns zero (it's now `http_envelope(...)`).
3. **Framework 404/405 also enveloped.** `test_error_envelope_builtin_404.py` covers both.
4. **`seq` contract locked.** `test_event_seq_monotonic.py` asserts strict monotonicity across types.
5. **All thirteen event types enumerated** in the agent guide (`join`, `leave`, `move`, `chat`, `reaction`, `lighting_changed`, `note_created`, `note_updated`, `note_deleted`, `stroke_added`, `stroke_dropped`, `board_cleared`, `vote_changed`).
6. **Coordination obligations honored.** No `actor_color` (spec #06). No `actor_position_at_event` (spec #02). No new event types (specs #05/#07/#11). No proximity logic (spec #02). Other specs can rely on the flat event shape and `http_envelope` helper being in place.
7. **Frontend types match backend.** `frontend/src/api/types.ts`'s `JoinEvent`/`MoveEvent`/`ChatEvent`/`LeaveEvent`/`ReactionEvent` reflect the new required fields. `ApiError`/`ApiErrorResponse` interfaces exported so callers can pattern-match `error.detail.error`.
8. **Defaults are sensible.** `envelope(code)` produces a useful `message` even when the route does not pass one — agents always have a human-readable string to surface.
