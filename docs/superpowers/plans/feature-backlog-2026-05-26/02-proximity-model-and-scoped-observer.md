# Proximity Model + Scoped Observer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/observe` return only what the requesting participant would plausibly see/hear from their current position — closing the noteboard-visible-at-distance bug systematically, and giving agents a "world" that actually has audible/visible distance. Emit one-shot `proximity_snapshot` events when the requester walks into earshot of someone or into a module's `interactionRect`, and `proximity_left` events when they walk out, so agents can reconcile local state without re-snapshotting.

**Architecture:** Three primitives land in `backend/app/world.py`:
1. `PROXIMITY_RADIUS = 180.0` — single source of truth. ~36% of the 800-wide world, ~1.5× the smallest zone (chill ≈ 272×140) and the largest module footprint (180×80). Big enough that a participant standing inside a zone usually hears the zone's other occupants; small enough that the far side of the room is muted.
2. `within_proximity(a, b) -> bool` — plain Euclidean distance, **walls do not block** (explicit out-of-scope for v1, see Open questions in feature-backlog §6).
3. `ProximityTracker` — per `(party_slug, requester_id)` state remembering which other participants and which modules the requester was inside-radius / inside-rect of on their previous poll. Lives as `PartyWorld._proximity_trackers: dict[str, ProximityTracker]` keyed by `requester_id`, cleared on `leave()`.

`/observe`'s `?since=` branch is rewritten so it scopes participants, events, and module state to the requester's current position, and emits `proximity_snapshot` / `proximity_left` events when entry/exit is detected. A new `room_wide: bool` flag on events (defaulting to `False`) lets specific event types opt into "always delivered regardless of proximity" — spec #03 will flip it on for broadcast chats, spec #07 for music, etc. `lighting_changed`, `board_cleared`, and `vote_changed` set `room_wide=True` from this spec since they're already room-global semantically.

**Tech Stack:** FastAPI (Python 3.11) backend, pytest + httpx. Frontend types updated additively.

**Assumes spec #01 has landed:** events expose flat `actor_id` / `actor_username` / `actor_kind`; error envelope is `{"detail": {"error": "...", "message": "..."}}`. This plan references those fields without redefining them.

---

## Out of scope (do not implement here)

- **Line-of-sight / wall occlusion.** Plain radius only. Walls are NOT consulted by `within_proximity()`. Documented in the agent guide so agents don't assume otherwise.
- **Chat `scope: "room"` vs `proximity`.** Spec #03 owns the chat-scope decision. This spec only adds the `room_wide` plumbing on events; spec #03 will set it on broadcast chats.
- **Module-scoped chat channel.** Spec #04 owns this. This spec only ensures module state is scoped to in-rect requesters.
- **`actor_color` propagation.** Spec #06 owns this. This spec touches participant payloads but does not add color fields.
- **`room.modules` vs top-level `modules` clarification.** Already handled by the 2026-05-20 plan.

---

## Spec → Task Map

| Backlog item | Task |
|---|---|
| §6 Owner Add: proximity-scoped `/observe` (participants) | Task 3 |
| §6 Owner Add: proximity-scoped `/observe` (events) | Task 4 |
| §4 BUG: notes visible at distance / §6 Owner Add: module state in-rect only | Task 5 |
| §6 Owner Add: catch-up snapshot on proximity entry | Task 6 |
| §6 Owner Add: proximity-leave events | Task 7 |
| Per-requester tracking (`ProximityTracker`) | Task 2 + threaded through 3-7 |
| `PROXIMITY_RADIUS` + `within_proximity()` helper | Task 1 |
| `room_wide` event flag | Task 1 |
| Agent guide update | Task 8 |
| Final verification + frontend types + CLAUDE.md | Task 9 |

---

## File Structure

**Backend — modify:**
- `backend/app/world.py` — add `PROXIMITY_RADIUS`, `within_proximity()`, `ProximityTracker`, scoped observer logic; clear tracker on `leave()`.
- `backend/app/events.py` — add `room_wide: bool = False` to all event models; add `ProximitySnapshotEvent` and `ProximityLeftEvent`; mark `LightingChangedEvent`, `BoardClearedEvent`, `VoteChangedEvent` as `room_wide=True` at construction sites.
- `backend/app/routes/party_actions.py` — pass requester id into `world.observe_since(since, requester_id=...)`; clear tracker on leave.
- `backend/app/routes/agent_guide.py` — document proximity radius, what's always-visible, snapshot/leave event shapes.

**Backend — new tests:**
- `backend/tests/test_proximity_helpers.py` — `within_proximity`, `PROXIMITY_RADIUS` constant.
- `backend/tests/test_observe_scoped_participants.py` — far-away participants hidden.
- `backend/tests/test_observe_scoped_events.py` — far-away chats/reactions/moves dropped; room-wide always pass through.
- `backend/tests/test_observe_scoped_modules.py` — note contents hidden at distance (the bug fix).
- `backend/tests/test_observe_proximity_snapshot.py` — one-shot snapshot on enter (module + participant).
- `backend/tests/test_observe_proximity_left.py` — leave event on exit.
- `backend/tests/test_proximity_tracker.py` — tracker cleared on `leave()`.

**Frontend — modify:**
- `frontend/src/api/types.ts` — add optional `room_wide?: boolean` to event types; add `ProximitySnapshotEvent` and `ProximityLeftEvent` interfaces; tweak observe response so `participants` and `modules[*].notes`/`modules[*].strokes`/`modules[*].vote` may be omitted/empty for out-of-range cases.

---

## Task 1: Add `PROXIMITY_RADIUS`, `within_proximity()`, and `room_wide` event flag

**Files:**
- Modify: `backend/app/world.py`
- Modify: `backend/app/events.py`
- Test: `backend/tests/test_proximity_helpers.py`

**Design decision:** `PROXIMITY_RADIUS = 180.0` world units. Justification: `cream-terrazzo` is 800×500; smallest zone (`chill`) is `34% × 28%` ≈ 272×140 units; modules are 180×80. A 180-unit radius is ~1.5× the larger module dimension and roughly one zone's width — enough that walking into a zone usually puts you in earshot of its other occupants without making the whole room audible. `room_wide` defaults to `False` so any future event type defaults to proximity-scoped.

- [ ] **Step 1: Write the failing helper test**

Create `backend/tests/test_proximity_helpers.py`:

```python
import math

from app.world import PROXIMITY_RADIUS, within_proximity


def test_proximity_radius_is_180():
    # Single source of truth — other specs reference this constant.
    assert PROXIMITY_RADIUS == 180.0


def test_within_proximity_zero_distance():
    assert within_proximity((100.0, 100.0), (100.0, 100.0)) is True


def test_within_proximity_just_inside():
    # 179 units east — inside the bubble.
    assert within_proximity((0.0, 0.0), (179.0, 0.0)) is True


def test_within_proximity_just_outside():
    # 181 units east — outside.
    assert within_proximity((0.0, 0.0), (181.0, 0.0)) is False


def test_within_proximity_diagonal():
    # 3-4-5 triangle scaled to ~180 hypotenuse: (108, 144) is exactly 180 away.
    assert within_proximity((0.0, 0.0), (108.0, 144.0)) is True
    # Just past — 109, 145 — distance > 180.
    assert within_proximity((0.0, 0.0), (109.0, 145.0)) is False


def test_within_proximity_ignores_walls():
    # Documentation-as-test: walls do NOT block proximity in v1.
    # The function takes only two points — there is no `walls` parameter.
    # If a future change adds a walls argument, update this test deliberately.
    assert within_proximity((0.0, 0.0), (50.0, 0.0)) is True
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_proximity_helpers.py -v`
Expected: FAIL — `PROXIMITY_RADIUS` and `within_proximity` do not exist.

- [ ] **Step 3: Implement the constant and helper**

In `backend/app/world.py`, near the top after imports and before `_LIGHTING_PRESETS`:

```python
import math

# Proximity radius in world units. See plan #02 for justification.
# Other specs MUST import this constant rather than redefining it.
PROXIMITY_RADIUS = 180.0


def within_proximity(
    a: tuple[float, float], b: tuple[float, float]
) -> bool:
    """Return True if points ``a`` and ``b`` are within PROXIMITY_RADIUS.

    Plain Euclidean radius. Walls do NOT block — line-of-sight is explicitly
    out of scope for v1 (see ``docs/features/feature-backlog.md`` §6 Owner
    Additions, Open question).
    """
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.hypot(dx, dy) <= PROXIMITY_RADIUS
```

- [ ] **Step 4: Add `room_wide` to event models**

In `backend/app/events.py`, add a `room_wide: bool = False` field to every event class. For events that are semantically room-global, override the default to `True` at construction time (Task 4) — keep the field default `False` so future event authors must opt in.

```python
class JoinEvent(BaseModel):
    seq: int
    type: Literal["join"] = "join"
    participant: Participant
    at: float
    room_wide: bool = False


class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"] = "leave"
    participant_id: str
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    room_wide: bool = False


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
    room_wide: bool = False


class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    participant_id: str
    text: str
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    room_wide: bool = False


class ReactionEvent(BaseModel):
    seq: int
    type: Literal["reaction"] = "reaction"
    actor_id: str
    emoji: str
    expires_at: float
    at: float
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    room_wide: bool = False


class LightingChangedEvent(BaseModel):
    seq: int
    type: Literal["lighting_changed"] = "lighting_changed"
    preset: Literal["day", "dusk", "night", "party"]
    changed_by: str
    at: float
    room_wide: bool = True  # lighting is a whole-room change


class NoteCreatedEvent(BaseModel):
    seq: int
    type: Literal["note_created"] = "note_created"
    module_id: str
    note: StickyNote
    at: float
    room_wide: bool = False


class NoteUpdatedEvent(BaseModel):
    seq: int
    type: Literal["note_updated"] = "note_updated"
    module_id: str
    note: StickyNote
    at: float
    room_wide: bool = False


class NoteDeletedEvent(BaseModel):
    seq: int
    type: Literal["note_deleted"] = "note_deleted"
    module_id: str
    note_id: str
    at: float
    room_wide: bool = False


class StrokeAddedEvent(BaseModel):
    seq: int
    type: Literal["stroke_added"] = "stroke_added"
    module_id: str
    stroke: Stroke
    at: float
    room_wide: bool = False


class StrokeDroppedEvent(BaseModel):
    seq: int
    type: Literal["stroke_dropped"] = "stroke_dropped"
    module_id: str
    stroke_id: str
    at: float
    room_wide: bool = False


class BoardClearedEvent(BaseModel):
    seq: int
    type: Literal["board_cleared"] = "board_cleared"
    module_id: str
    cleared_by: str
    at: float
    room_wide: bool = True  # visible to everyone — the board snaps clean


class VoteChangedEvent(BaseModel):
    seq: int
    type: Literal["vote_changed"] = "vote_changed"
    module_id: str
    votes: int
    needed: int
    at: float
    room_wide: bool = True  # tally visible to everyone watching the board
```

Also add the two new proximity event models at the end of the file (above the `Event` union):

```python
class ProximitySnapshotEvent(BaseModel):
    """One-shot snapshot emitted to a specific requester when they enter
    proximity of a module's interactionRect or another participant.

    Server-side only: NEVER appended to ``PartyWorld._events`` because it is
    per-requester. Constructed on the fly inside ``observe_since`` and
    injected into that requester's event list.
    """

    seq: int  # mirrors the cursor at emit time so clients can sort/dedupe
    type: Literal["proximity_snapshot"] = "proximity_snapshot"
    at: float
    entered: dict  # {"kind": "module"|"participant", "id": "..."}
    # Populated when entered.kind == "module":
    module: dict | None = None  # full module snapshot (notes/strokes/vote)
    # Populated when entered.kind == "participant":
    recent_chat: list[dict] | None = None  # last N visible chats from them
    room_wide: bool = False


class ProximityLeftEvent(BaseModel):
    """One-shot leave event when the requester walks out of range of a
    participant or out of a module's interactionRect."""

    seq: int
    type: Literal["proximity_left"] = "proximity_left"
    at: float
    left: dict  # {"kind": "module"|"participant", "id": "..."}
    room_wide: bool = False
```

Extend the `Event` union (note: these synthetic events do NOT actually flow through the shared event log; the union is for type completeness on the wire):

```python
Event = (
    JoinEvent
    | LeaveEvent
    | MoveEvent
    | ChatEvent
    | ReactionEvent
    | LightingChangedEvent
    | NoteCreatedEvent
    | NoteUpdatedEvent
    | NoteDeletedEvent
    | StrokeAddedEvent
    | StrokeDroppedEvent
    | BoardClearedEvent
    | VoteChangedEvent
    | ProximitySnapshotEvent
    | ProximityLeftEvent
)
```

- [ ] **Step 5: Re-run helper test, confirm pass**

Run: `cd backend && python -m pytest tests/test_proximity_helpers.py -v`
Expected: PASS.

- [ ] **Step 6: Run full backend suite to make sure `room_wide` doesn't break anything**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS. The new field is optional with a default, so existing event-equality assertions that use subset comparisons (per the 2026-05-20 plan) keep passing. If any test asserts exact dict equality on a `lighting_changed`/`board_cleared`/`vote_changed` dump, update it to expect `room_wide=True`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/world.py backend/app/events.py \
        backend/tests/test_proximity_helpers.py
git commit -m "feat(proximity): add PROXIMITY_RADIUS, within_proximity helper, room_wide flag"
```

---

## Task 2: `ProximityTracker` — per-requester memory of last in-range set

**Files:**
- Modify: `backend/app/world.py`
- Test: `backend/tests/test_proximity_tracker.py`

**Design decision:** Tracker is keyed by `requester_id` and stored on `PartyWorld` (so a server restart loses it cleanly; matches the in-memory world model). The tracker records two sets — `participants_in_range: set[str]` and `modules_in_rect: set[str]` — and exposes a `diff(now_participants, now_modules) -> (entered, left)` method. The tracker also remembers `last_observed_cursor: int` per requester so we know which of that participant's chats are "new since you saw them" when building the catch-up snapshot in Task 6. Tracker entries are cleared on `world.leave(participant_id)` for that participant. There is no eviction policy for tracker entries left behind by HTTP-only never-joined requesters — agents always go through `/join` first, and the dict grows at most linearly with unique joiners until process restart.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_proximity_tracker.py`:

```python
from tests.conftest import join_party, register_human


def test_tracker_cleared_on_leave(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")

    # Alice polls — establishes a tracker entry.
    client.get("/api/parties/cream-terrazzo/observe", params={"principal_id": a["principal"]["id"]})

    # Internal check via the store.
    from app.main import app  # noqa: WPS433 - test introspection
    from app.store import Store
    store: Store = app.state.store
    world = store.get_or_create_world("cream-terrazzo")
    assert a["principal"]["id"] in world._proximity_trackers

    # Alice leaves → tracker cleared.
    client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": a["principal"]},
    )
    assert a["principal"]["id"] not in world._proximity_trackers


def test_tracker_diff_detects_entry_and_exit():
    from app.world import ProximityTracker

    t = ProximityTracker()
    entered_p, left_p, entered_m, left_m = t.diff(
        participants_in_range={"alice", "bob"},
        modules_in_rect={"draw-1"},
    )
    assert entered_p == {"alice", "bob"}
    assert left_p == set()
    assert entered_m == {"draw-1"}
    assert left_m == set()

    entered_p, left_p, entered_m, left_m = t.diff(
        participants_in_range={"bob", "carol"},
        modules_in_rect=set(),
    )
    assert entered_p == {"carol"}
    assert left_p == {"alice"}
    assert entered_m == set()
    assert left_m == {"draw-1"}
```

Note: the `/observe` route currently does not accept a `principal_id` query parameter. Task 3 will add the **principal** parameter so scoping can happen. For now, this test reads the tracker dict directly via the store, which is a stable internal API.

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_proximity_tracker.py -v`
Expected: FAIL — `ProximityTracker` and `world._proximity_trackers` do not exist.

- [ ] **Step 3: Implement `ProximityTracker`**

In `backend/app/world.py`, add the class above `class PartyWorld:`:

```python
class ProximityTracker:
    """Per-requester memory of which participants and modules they were in
    range of on their last ``observe_since`` call.

    Used to detect proximity entry (emit ``proximity_snapshot``) and
    proximity exit (emit ``proximity_left``). Owned by ``PartyWorld``,
    keyed by requester participant id, cleared on ``leave``.
    """

    def __init__(self) -> None:
        self.participants_in_range: set[str] = set()
        self.modules_in_rect: set[str] = set()
        # The cursor at the time of the last poll. Used to bound the
        # ``recent_chat`` slice in a participant-entry snapshot to chats
        # the requester hadn't yet seen.
        self.last_observed_cursor: int = 0

    def diff(
        self,
        participants_in_range: set[str],
        modules_in_rect: set[str],
    ) -> tuple[set[str], set[str], set[str], set[str]]:
        entered_p = participants_in_range - self.participants_in_range
        left_p = self.participants_in_range - participants_in_range
        entered_m = modules_in_rect - self.modules_in_rect
        left_m = self.modules_in_rect - modules_in_rect
        return entered_p, left_p, entered_m, left_m

    def commit(
        self,
        participants_in_range: set[str],
        modules_in_rect: set[str],
        cursor: int,
    ) -> None:
        self.participants_in_range = set(participants_in_range)
        self.modules_in_rect = set(modules_in_rect)
        self.last_observed_cursor = cursor
```

Wire it into `PartyWorld.__init__`:

```python
self._proximity_trackers: dict[str, ProximityTracker] = {}
```

Clear it in `PartyWorld.leave`, after capturing actor fields and before deleting from `participants`:

```python
def leave(self, participant_id: str) -> LeaveEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    actor = self._actor_fields(participant_id)
    del self.participants[participant_id]
    self._proximity_trackers.pop(participant_id, None)  # NEW
    ev = LeaveEvent(
        seq=self._next_seq(),
        participant_id=participant_id,
        at=time.time(),
        **actor,
    )
    ...
```

- [ ] **Step 4: Run the tracker test, confirm pass**

Run: `cd backend && python -m pytest tests/test_proximity_tracker.py -v`
Expected: The `test_tracker_diff_detects_entry_and_exit` test passes. `test_tracker_cleared_on_leave` will still fail because the tracker isn't created yet — that happens in Task 3. **Defer the first test for now** by marking it `@pytest.mark.xfail(reason="tracker created in task 3")` or leaving it failing and fixing it in Task 3. Recommended: leave it failing (TDD red) and continue.

- [ ] **Step 5: Commit**

```bash
git add backend/app/world.py backend/tests/test_proximity_tracker.py
git commit -m "feat(proximity): add ProximityTracker (per-requester in-range memory)"
```

---

## Task 3: Scoped `/observe` — participants

**Files:**
- Modify: `backend/app/world.py` — `observe_since` becomes per-requester.
- Modify: `backend/app/routes/party_actions.py` — observe endpoint accepts `principal` and threads requester id through.
- Test: `backend/tests/test_observe_scoped_participants.py`

**Design decision:** The `/observe` route currently has no notion of "who is asking." We change `?since=` polls to require a principal so we can compute proximity. To keep backwards compat for legacy callers (e.g. existing frontend `useRealtimeParty` and the snapshot UI), we make the principal **optional**: when absent, fall back to unscoped behavior (snapshot or full-event observe_since). When present, the response is scoped.

Pass principal as query params `principal_id` and `principal_kind` (the same shape as the body — flat for GET requests).

**Design decision: participants list "feel".** Out-of-range participants are OMITTED ENTIRELY from `participants` (no id, no username, no color). This keeps the world feel mysterious — you literally can't see someone across the wall. Document this in the agent guide so agents don't get confused when a participant they previously saw vanishes from `participants`. (They'll still appear in `proximity_left` events for the transition.)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_observe_scoped_participants.py`:

```python
from tests.conftest import join_party, register_human


def _observe(client, principal, since=None):
    params = {
        "principal_id": principal["principal"]["id"],
        "principal_kind": principal["principal"]["kind"],
    }
    if since is not None:
        params["since"] = since
    return client.get("/api/parties/cream-terrazzo/observe", params=params).json()


def test_initial_observe_hides_far_away_participants(client):
    # Alice spawns at (50, 50); Bob spawns at (750, 450) — distance > 180.
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)

    obs = _observe(client, a)
    ids = {p["id"] for p in obs["participants"]}
    assert a["principal"]["id"] in ids
    assert b["principal"]["id"] not in ids, (
        "Bob is across the room — should be hidden"
    )


def test_initial_observe_includes_in_range_participants(client):
    a = register_human(client, username="Alice")
    c = register_human(client, username="Carol")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    join_party(client, c, "cream-terrazzo", x=200, y=150)  # ~111 units away

    obs = _observe(client, a)
    ids = {p["id"] for p in obs["participants"]}
    assert c["principal"]["id"] in ids


def test_legacy_observe_without_principal_returns_all_participants(client):
    # Backwards compat: no principal_id → unscoped (frontend renderer relies
    # on this until it migrates).
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)

    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    ids = {p["id"] for p in obs["participants"]}
    assert {a["principal"]["id"], b["principal"]["id"]} <= ids
```

`tests/conftest.py`'s `join_party` may not accept `x`/`y` keyword args. Check and either extend it (preferred — small additive helper) or inline a follow-up `POST /move` after each join. Recommended: extend `join_party`:

```python
def join_party(client, sess, slug, *, x=None, y=None):
    body = {"principal": sess["principal"]}
    if x is not None:
        body["x"] = x
    if y is not None:
        body["y"] = y
    return client.post(f"/api/parties/{slug}/join", json=body).json()
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_observe_scoped_participants.py -v`
Expected: FAIL — observe ignores the requester's position.

- [ ] **Step 3: Add scoped helpers in `world.py`**

In `backend/app/world.py`, add to `PartyWorld`:

```python
def _participants_visible_to(self, requester_id: str) -> list[dict]:
    """Project participants the requester can see (within radius)."""
    req = self.participants.get(requester_id)
    if req is None:
        # Caller asked about themselves but they're not in the party.
        return []
    out: list[dict] = []
    for p in self.participants.values():
        if p.id == requester_id or within_proximity(
            (req.x, req.y), (p.x, p.y)
        ):
            out.append(self._participant_dict(p))
    return out

def _modules_in_rect_for(self, requester_id: str) -> set[str]:
    req = self.participants.get(requester_id)
    if req is None:
        return set()
    out: set[str] = set()
    for m in self._party.modules:
        if isinstance(m, (StickyNoteModule, DrawBoardModule)):
            if self.in_zone(m.id, req.x, req.y):
                out.add(m.id)
    return out

def _participants_in_range_for(self, requester_id: str) -> set[str]:
    req = self.participants.get(requester_id)
    if req is None:
        return set()
    return {
        p.id
        for p in self.participants.values()
        if p.id != requester_id and within_proximity(
            (req.x, req.y), (p.x, p.y)
        )
    }

def scoped_snapshot(self, requester_id: str) -> dict:
    """``snapshot()`` filtered to what the requester can see."""
    base = self.snapshot()
    base["participants"] = self._participants_visible_to(requester_id)
    in_rect = self._modules_in_rect_for(requester_id)
    base["modules"] = [
        m if m["id"] in in_rect else self._module_stub(m)
        for m in base["modules"]
    ]
    return base

def _module_stub(self, full: dict) -> dict:
    """Strip live state from a module the requester is not inside.

    Keeps placement / approachSlots so agents can navigate toward it, but
    omits ``notes``/``strokes``/``vote`` so distant module state stays
    hidden (fixes the noteboard-at-distance bug).
    """
    stub = {
        k: v for k, v in full.items()
        if k not in ("notes", "strokes", "vote")
    }
    return stub
```

- [ ] **Step 4: Make `observe` endpoint accept a principal**

In `backend/app/routes/party_actions.py`:

```python
@router.get("/{slug}/observe")
def observe(
    slug: str = Path(pattern=_SLUG_PATTERN),
    since: int | None = None,
    principal_id: str | None = None,
    principal_kind: str | None = None,
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    party = store.get_party(slug)
    assert party is not None

    requester_id: str | None = None
    if principal_id is not None and principal_kind is not None:
        # Best-effort: only scope if the requester is actually in the party.
        # If the principal is unknown/not joined, fall back to unscoped so
        # the lobby UI still works.
        if principal_id in world.participants:
            requester_id = principal_id

    if since is None:
        if requester_id is None:
            snap = world.snapshot()
        else:
            snap = world.scoped_snapshot(requester_id)
        return {
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
            "modules": snap["modules"],
            "lighting": snap["lighting"],
            "active_reactions": snap["active_reactions"],
            "recent_chat": world.recent_chat(),
        }
    if requester_id is None:
        return world.observe_since(since)
    return world.observe_since_scoped(since, requester_id)
```

Add a stub `observe_since_scoped` on the world that for now just delegates to `observe_since` — Task 4 fills it in. This keeps the test green for participants while we iterate:

```python
def observe_since_scoped(self, since: int, requester_id: str) -> dict:
    # Filled out in Task 4. For now: filter participants via the snapshot
    # path; events scoping comes next.
    base = self.observe_since(since)
    # We don't trim events yet — Task 4 handles that.
    return base
```

- [ ] **Step 5: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_observe_scoped_participants.py -v`
Expected: PASS — the *initial* (no-`since`) call already scopes participants via `scoped_snapshot`. The `since`-branch tests come in Task 4.

- [ ] **Step 6: Also re-run the deferred tracker test from Task 2**

Run: `cd backend && python -m pytest tests/test_proximity_tracker.py -v`
Expected: still FAIL on `test_tracker_cleared_on_leave` — the tracker isn't yet created in the observe path. That happens in Task 4 (when `observe_since_scoped` actually uses one). Leave failing.

- [ ] **Step 7: Run full backend suite**

Run: `cd backend && python -m pytest -x --tb=short --ignore=backend/tests/test_proximity_tracker.py --ignore=backend/tests/test_observe_scoped_modules.py --ignore=backend/tests/test_observe_proximity_snapshot.py --ignore=backend/tests/test_observe_proximity_left.py --ignore=backend/tests/test_observe_scoped_events.py`
Expected: ALL PASS (excluding the WIP files we'll add in later tasks).

- [ ] **Step 8: Commit**

```bash
git add backend/app/world.py backend/app/routes/party_actions.py \
        backend/tests/conftest.py backend/tests/test_observe_scoped_participants.py
git commit -m "feat(observe): scope participants to within PROXIMITY_RADIUS of requester"
```

---

## Task 4: Scoped events — drop far-away chats/reactions/moves; pass room_wide through

**Files:**
- Modify: `backend/app/world.py` — flesh out `observe_since_scoped`.
- Test: `backend/tests/test_observe_scoped_events.py`

**Design decision:** Event scoping happens at the actor's position **at the time the event was emitted**. We record actor position into a small log alongside events for chat/reaction/move events (we have it for `MoveEvent.x/y` already; for chat/reaction we look up the participant's position from the most recent prior `MoveEvent` of that actor, or fall back to their current position which is a known approximation). To keep things simple and correct: cache `actor_position_at_event` in a side dict keyed by `seq`, populated by the `chat`/`react` methods at emit time using the actor's current position. (`move` events carry x/y already.)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_observe_scoped_events.py`:

```python
from tests.conftest import join_party, register_human


def _observe(client, principal, since):
    return client.get(
        "/api/parties/cream-terrazzo/observe",
        params={
            "principal_id": principal["principal"]["id"],
            "principal_kind": principal["principal"]["kind"],
            "since": since,
        },
    ).json()


def test_chat_from_far_participant_is_dropped(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)
    cur = _observe(client, a, since=0)["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": b["principal"], "text": "hello from far away"},
    )

    diff = _observe(client, a, since=cur)
    chats = [e for e in diff["events"] if e["type"] == "chat"]
    assert chats == [], "Bob's chat should be inaudible from across the room"


def test_chat_from_nearby_participant_passes(client):
    a = register_human(client, username="Alice")
    c = register_human(client, username="Carol")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    join_party(client, c, "cream-terrazzo", x=200, y=150)
    cur = _observe(client, a, since=0)["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": c["principal"], "text": "hi neighbor"},
    )
    diff = _observe(client, a, since=cur)
    chats = [e for e in diff["events"] if e["type"] == "chat"]
    assert any(c["text"] == "hi neighbor" for c in chats)


def test_far_move_is_dropped(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)
    cur = _observe(client, a, since=0)["cursor"]

    # Bob moves but stays far.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 740, "y": 440},
    )
    diff = _observe(client, a, since=cur)
    moves = [e for e in diff["events"] if e["type"] == "move"]
    assert moves == []


def test_lighting_change_always_visible(client):
    # room_wide events bypass proximity scoping.
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)
    cur = _observe(client, a, since=0)["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": b["principal"], "preset": "night"},
    )
    diff = _observe(client, a, since=cur)
    lights = [e for e in diff["events"] if e["type"] == "lighting_changed"]
    assert len(lights) == 1


def test_reaction_far_dropped_near_kept(client):
    a = register_human(client, username="Alice")
    far = register_human(client, username="Far")
    near = register_human(client, username="Near")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    join_party(client, far, "cream-terrazzo", x=700, y=400)
    join_party(client, near, "cream-terrazzo", x=180, y=180)
    cur = _observe(client, a, since=0)["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": far["principal"], "emoji": "🔥"},
    )
    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": near["principal"], "emoji": "👍"},
    )
    diff = _observe(client, a, since=cur)
    rx = [e for e in diff["events"] if e["type"] == "reaction"]
    emojis = {r["emoji"] for r in rx}
    assert "🔥" not in emojis
    assert "👍" in emojis
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_observe_scoped_events.py -v`
Expected: FAIL — events from far participants still leak through.

- [ ] **Step 3: Record actor position at chat/react emit time**

In `backend/app/world.py`:

1. Add a side cache on `PartyWorld.__init__`:

```python
# Position of the actor at the time each event was emitted, keyed by seq.
# Only populated for chat/reaction events; move events carry x/y already.
self._actor_pos_at_seq: dict[int, tuple[float, float]] = {}
```

2. In `chat`, after constructing `ev`:

```python
self._actor_pos_at_seq[ev.seq] = (sender.x, sender.y)
```

3. In `react`, after constructing `ev`:

```python
p = self.participants[participant_id]
self._actor_pos_at_seq[ev.seq] = (p.x, p.y)
```

- [ ] **Step 4: Implement `observe_since_scoped` with event scoping**

Replace the placeholder `observe_since_scoped` with:

```python
def observe_since_scoped(self, since: int, requester_id: str) -> dict:
    if since < 0:
        since = 0
    req = self.participants.get(requester_id)
    if req is None:
        # Requester left mid-poll — return unscoped tail.
        return self.observe_since(since)

    tracker = self._proximity_trackers.setdefault(
        requester_id, ProximityTracker()
    )

    tail = self._events[since:]
    latest_move_by_pid: dict[str, MoveEvent] = {}
    latest_vote_by_module: dict[str, VoteChangedEvent] = {}
    out: list[dict] = []

    req_pos = (req.x, req.y)

    for ev in tail:
        # room_wide events always pass.
        room_wide = getattr(ev, "room_wide", False)

        if isinstance(ev, MoveEvent):
            # Coalesce to latest, but scope by actor's *final* move position
            # relative to the requester.
            if room_wide or within_proximity(req_pos, (ev.x, ev.y)):
                latest_move_by_pid[ev.participant_id] = ev
            continue

        if isinstance(ev, VoteChangedEvent):
            # room_wide by default — but still coalesce.
            latest_vote_by_module[ev.module_id] = ev
            continue

        if isinstance(ev, ChatEvent):
            if not room_wide:
                pos = self._actor_pos_at_seq.get(ev.seq)
                if pos is None or not within_proximity(req_pos, pos):
                    continue
            out.append(ev.model_dump())
            continue

        if isinstance(ev, ReactionEvent):
            if not room_wide:
                pos = self._actor_pos_at_seq.get(ev.seq)
                if pos is None or not within_proximity(req_pos, pos):
                    continue
            out.append(ev.model_dump())
            continue

        if isinstance(
            ev,
            (NoteCreatedEvent, NoteUpdatedEvent, NoteDeletedEvent,
             StrokeAddedEvent, StrokeDroppedEvent),
        ):
            # Module-scoped events: only delivered if requester is inside
            # the module's interactionRect right now.
            if self.in_zone(ev.module_id, req.x, req.y):
                out.append(ev.model_dump())
            continue

        if isinstance(ev, JoinEvent):
            jp = ev.participant
            if within_proximity(req_pos, (jp.x, jp.y)):
                out.append(
                    {
                        "type": "join",
                        "seq": ev.seq,
                        "participant": self._participant_dict(jp),
                        "at": ev.at,
                        "room_wide": False,
                    }
                )
            continue

        if isinstance(ev, LeaveEvent):
            # Always deliver leave so requester can clean up local state —
            # but only if the leaver was previously visible to them.
            # Simpler: always deliver; clients can ignore unknown ids.
            out.append(ev.model_dump())
            continue

        # Default: room_wide or unrecognized → pass through.
        if room_wide:
            out.append(ev.model_dump())

    for mv in latest_move_by_pid.values():
        d = mv.model_dump()
        d["zone"] = self.derive_zone(mv.x, mv.y)
        out.append(d)
    for v in latest_vote_by_module.values():
        out.append(v.model_dump())

    out.sort(key=lambda e: e["seq"])

    # Update tracker. Snapshot the current proximity sets so Task 6 / 7 can
    # diff them. We update LAST so the snapshot/leave logic added in Task 6/7
    # can see the previous state via tracker.diff() before commit.
    tracker.commit(
        participants_in_range=self._participants_in_range_for(requester_id),
        modules_in_rect=self._modules_in_rect_for(requester_id),
        cursor=self.cursor,
    )

    return {"events": out, "cursor": self.cursor}
```

- [ ] **Step 5: Re-run the events test, confirm pass**

Run: `cd backend && python -m pytest tests/test_observe_scoped_events.py -v`
Expected: PASS.

- [ ] **Step 6: Re-run the tracker test from Task 2**

Run: `cd backend && python -m pytest tests/test_proximity_tracker.py -v`
Expected: PASS now — `observe_since_scoped` materializes the tracker entry.

- [ ] **Step 7: Run full suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/world.py backend/tests/test_observe_scoped_events.py
git commit -m "feat(observe): scope events by actor position; room_wide bypasses"
```

---

## Task 5: Module state hidden at distance — fixes the noteboard-at-distance bug

**Files:**
- Modify: `backend/app/world.py` (already largely covered by `scoped_snapshot` in Task 3, but lock with a dedicated regression test).
- Test: `backend/tests/test_observe_scoped_modules.py`

This task is the explicit regression test for the §4 BUG ("Notes visible at distance"). `scoped_snapshot` already calls `_module_stub` for modules whose `interactionRect` does not contain the requester. We add a test that reproduces the bug pre-fix (would have passed before Task 3) and confirms the fix holds.

- [ ] **Step 1: Write the test**

Create `backend/tests/test_observe_scoped_modules.py`:

```python
from tests.conftest import join_party, register_human


def _observe(client, principal, since=None):
    params = {
        "principal_id": principal["principal"]["id"],
        "principal_kind": principal["principal"]["kind"],
    }
    if since is not None:
        params["since"] = since
    return client.get(
        "/api/parties/cream-terrazzo/observe", params=params
    ).json()


def _move_into(client, sess, module):
    ir = module["interactionRect"]
    cx = ir["x"] + ir["w"] / 2
    cy = ir["y"] + ir["h"] / 2
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": sess["principal"], "x": cx, "y": cy},
    )


def test_notes_hidden_when_requester_not_in_module_rect(client):
    # Bug reproduction: Alice writes a note; Bob — standing across the
    # room — should NOT see the note contents in /observe.
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")

    # Find the sticky module from an unscoped initial observe.
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")

    _move_into(client, a, sticky)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={
            "principal": a["principal"],
            "text": "private",
            "color": "yellow",
            "x": 10,
            "y": 10,
        },
    )

    # Bob stays at spawn (far from sticky), and asks for a scoped observe.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 600, "y": 100},
    )
    obs = _observe(client, b)
    bob_sticky = next(m for m in obs["modules"] if m["id"] == sticky["id"])
    # The stub does not include `notes`.
    assert "notes" not in bob_sticky, (
        "Bob is not at the noteboard — note contents must be hidden"
    )


def test_notes_visible_when_requester_in_module_rect(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")
    _move_into(client, a, sticky)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={"principal": a["principal"], "text": "hi",
              "color": "yellow", "x": 10, "y": 10},
    )
    obs = _observe(client, a)
    sticky2 = next(m for m in obs["modules"] if m["id"] == sticky["id"])
    assert sticky2.get("notes"), "Alice is at the noteboard — should see notes"
    assert sticky2["notes"][0]["text"] == "hi"


def test_strokes_and_vote_hidden_when_not_at_drawboard(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    draw = next(m for m in initial["modules"] if m["kind"] == "drawboard")
    _move_into(client, a, draw)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{draw['id']}/strokes",
        json={
            "principal": a["principal"],
            "color": "#ffd54f",
            "width": "med",
            "points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}],
        },
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 100, "y": 100},
    )
    obs = _observe(client, b)
    db = next(m for m in obs["modules"] if m["id"] == draw["id"])
    assert "strokes" not in db
    assert "vote" not in db


def test_module_event_only_delivered_to_in_rect_requester(client):
    # While Bob is not in the noteboard rect, a note_created emitted by
    # Alice should NOT appear in Bob's diff.
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")
    _move_into(client, a, sticky)
    # Bob takes a cursor far from the sticky module.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 600, "y": 100},
    )
    cur = _observe(client, b)["cursor"]

    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={"principal": a["principal"], "text": "secret",
              "color": "yellow", "x": 10, "y": 10},
    )
    diff = _observe(client, b, since=cur)
    note_events = [e for e in diff["events"] if e["type"] == "note_created"]
    assert note_events == []
```

- [ ] **Step 2: Run, confirm pass on the first two and the last (Task 3 already wired scoped_snapshot; Task 4 wired note_created scoping)**

Run: `cd backend && python -m pytest tests/test_observe_scoped_modules.py -v`
Expected: PASS — this task is mostly a regression net for Tasks 3 + 4.

If the test fails (e.g. on `test_strokes_and_vote_hidden_when_not_at_drawboard`), inspect `_module_stub` — ensure it strips all three keys (`notes`, `strokes`, `vote`).

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_observe_scoped_modules.py
git commit -m "test(observe): lock the noteboard-at-distance bug fix"
```

---

## Task 6: `proximity_snapshot` event on entry

**Files:**
- Modify: `backend/app/world.py` — emit `proximity_snapshot` inside `observe_since_scoped` when tracker diff shows new entries.
- Test: `backend/tests/test_observe_proximity_snapshot.py`

**Design decision: shape and timing.**
- `entered: {kind: "module"|"participant", id: "..."}`
- For modules: `module: <full module snapshot from `_module_snapshot`>` so the agent gets the same shape they'd see in the initial snapshot's `modules[*]`.
- For participants: `recent_chat: [...]` containing up to `PROXIMITY_SNAPSHOT_CHAT_LIMIT = 5` of that participant's most recent chats whose `seq` is `<= cursor` AND `> tracker.last_observed_cursor` (i.e. chats the requester hadn't yet seen, drawn from the world chat log irrespective of proximity at emit — because the agent is "catching up" on what was just said).
- One-shot: emitted only on the poll where the entry is detected (i.e. tracker did not previously contain the id). The next poll won't repeat it.
- `seq`: assigned `self.cursor + 1, +2, ...` as synthetic seqs ahead of the real cursor; they sort to the end of `out`. (We do NOT bump `self._events` — synthetic per-requester events live only on the wire.)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_observe_proximity_snapshot.py`:

```python
from tests.conftest import join_party, register_human


def _observe(client, principal, since=None):
    params = {
        "principal_id": principal["principal"]["id"],
        "principal_kind": principal["principal"]["kind"],
    }
    if since is not None:
        params["since"] = since
    return client.get(
        "/api/parties/cream-terrazzo/observe", params=params
    ).json()


def _move_into(client, sess, module):
    ir = module["interactionRect"]
    cx = ir["x"] + ir["w"] / 2
    cy = ir["y"] + ir["h"] / 2
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": sess["principal"], "x": cx, "y": cy},
    )


def test_module_entry_fires_proximity_snapshot_once(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")

    # Pre-populate a note from another participant so the snapshot has content.
    b = register_human(client, username="Bob")
    join_party(client, b, "cream-terrazzo")
    _move_into(client, b, sticky)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={"principal": b["principal"], "text": "hello world",
              "color": "yellow", "x": 5, "y": 5},
    )
    # Bob steps away so Alice's entry is unambiguous.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 50, "y": 50},
    )

    # Alice's first scoped poll establishes baseline tracker state.
    obs0 = _observe(client, a)
    cur = obs0["cursor"]

    # Alice walks into the sticky rect.
    _move_into(client, a, sticky)
    diff = _observe(client, a, since=cur)
    snaps = [e for e in diff["events"] if e["type"] == "proximity_snapshot"]
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap["entered"] == {"kind": "module", "id": sticky["id"]}
    assert snap["module"] is not None
    assert any(n["text"] == "hello world" for n in snap["module"]["notes"])

    # Polling again WITHOUT moving — snapshot must NOT repeat.
    diff2 = _observe(client, a, since=diff["cursor"])
    repeats = [
        e for e in diff2["events"] if e["type"] == "proximity_snapshot"
    ]
    assert repeats == []


def test_participant_entry_fires_proximity_snapshot_with_recent_chat(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    # Bob is initially far from Alice.
    join_party(client, b, "cream-terrazzo", x=700, y=400)

    # Bob says things while far — Alice should NOT see them in real time.
    for i in range(3):
        client.post(
            "/api/parties/cream-terrazzo/chat",
            json={"principal": b["principal"], "text": f"far msg {i}"},
        )

    obs0 = _observe(client, a)
    cur = obs0["cursor"]

    # Bob walks into proximity of Alice.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 200, "y": 150},
    )

    diff = _observe(client, a, since=cur)
    snaps = [
        e for e in diff["events"]
        if e["type"] == "proximity_snapshot"
        and e["entered"]["kind"] == "participant"
        and e["entered"]["id"] == b["principal"]["id"]
    ]
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap["recent_chat"], "snapshot should include Bob's catch-up chats"
    texts = [c["text"] for c in snap["recent_chat"]]
    assert "far msg 2" in texts
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_observe_proximity_snapshot.py -v`
Expected: FAIL — no snapshot events emitted.

- [ ] **Step 3: Implement snapshot emission**

In `backend/app/world.py`:

1. Add a module-level constant near `PROXIMITY_RADIUS`:

```python
PROXIMITY_SNAPSHOT_CHAT_LIMIT = 5
```

2. Add a helper:

```python
def _participant_recent_chat(
    self, participant_id: str, after_seq: int, limit: int
) -> list[dict]:
    """Return up to ``limit`` most-recent chats from ``participant_id`` with
    ``seq > after_seq``, oldest-first."""
    out: list[dict] = []
    for ev in reversed(self._events):
        if (
            isinstance(ev, ChatEvent)
            and ev.participant_id == participant_id
            and ev.seq > after_seq
        ):
            out.append(ev.model_dump())
            if len(out) >= limit:
                break
    out.reverse()
    return out
```

3. Inside `observe_since_scoped`, BEFORE `tracker.commit(...)`, compute and append the proximity-snapshot events. Place this block immediately after the existing event-coalesce loop (after the `latest_move_by_pid` / `latest_vote_by_module` post-processing, before `out.sort(...)`):

```python
# --- Proximity entry: emit one-shot snapshots ---
now_participants = self._participants_in_range_for(requester_id)
now_modules = self._modules_in_rect_for(requester_id)
entered_p, _left_p, entered_m, _left_m = tracker.diff(
    now_participants, now_modules
)
synthetic_seq = self.cursor  # base; we'll bump per snapshot
now_ts = time.time()
for module_id in sorted(entered_m):
    m = self._placed_module(module_id)
    if m is None:
        continue
    synthetic_seq += 1
    out.append(
        {
            "type": "proximity_snapshot",
            "seq": synthetic_seq,
            "at": now_ts,
            "entered": {"kind": "module", "id": module_id},
            "module": self._module_snapshot(m),
            "recent_chat": None,
            "room_wide": False,
        }
    )
for other_id in sorted(entered_p):
    synthetic_seq += 1
    out.append(
        {
            "type": "proximity_snapshot",
            "seq": synthetic_seq,
            "at": now_ts,
            "entered": {"kind": "participant", "id": other_id},
            "module": None,
            "recent_chat": self._participant_recent_chat(
                other_id,
                after_seq=tracker.last_observed_cursor,
                limit=PROXIMITY_SNAPSHOT_CHAT_LIMIT,
            ),
            "room_wide": False,
        }
    )
```

Note: the `tracker.commit(...)` call already follows. The commit MUST stay after the diff so subsequent polls see the new state.

- [ ] **Step 4: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_observe_proximity_snapshot.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/world.py backend/app/events.py \
        backend/tests/test_observe_proximity_snapshot.py
git commit -m "feat(observe): emit one-shot proximity_snapshot on entry"
```

---

## Task 7: `proximity_left` event on exit

**Files:**
- Modify: `backend/app/world.py` — emit `proximity_left` from the same diff.
- Test: `backend/tests/test_observe_proximity_left.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_observe_proximity_left.py`:

```python
from tests.conftest import join_party, register_human


def _observe(client, principal, since=None):
    params = {
        "principal_id": principal["principal"]["id"],
        "principal_kind": principal["principal"]["kind"],
    }
    if since is not None:
        params["since"] = since
    return client.get(
        "/api/parties/cream-terrazzo/observe", params=params
    ).json()


def _move(client, sess, x, y):
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": sess["principal"], "x": x, "y": y},
    )


def test_walking_out_of_participant_proximity_fires_proximity_left(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    join_party(client, b, "cream-terrazzo", x=200, y=150)  # in range
    # Establish baseline.
    cur = _observe(client, a)["cursor"]

    # Alice walks away — Bob exits her bubble.
    _move(client, a, 600, 400)

    diff = _observe(client, a, since=cur)
    leaves = [
        e for e in diff["events"]
        if e["type"] == "proximity_left"
        and e["left"]["kind"] == "participant"
        and e["left"]["id"] == b["principal"]["id"]
    ]
    assert len(leaves) == 1

    # No repeat on next poll.
    diff2 = _observe(client, a, since=diff["cursor"])
    repeats = [
        e for e in diff2["events"] if e["type"] == "proximity_left"
    ]
    assert repeats == []


def test_walking_out_of_module_rect_fires_proximity_left(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")
    ir = sticky["interactionRect"]
    _move(client, a, ir["x"] + ir["w"] / 2, ir["y"] + ir["h"] / 2)

    # Baseline observe — tracker now records Alice inside the sticky rect.
    cur = _observe(client, a)["cursor"]

    # Alice walks away.
    _move(client, a, 400, 100)

    diff = _observe(client, a, since=cur)
    leaves = [
        e for e in diff["events"]
        if e["type"] == "proximity_left"
        and e["left"] == {"kind": "module", "id": sticky["id"]}
    ]
    assert len(leaves) == 1
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_observe_proximity_left.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement leave emission**

In `backend/app/world.py`, augment the `observe_since_scoped` block from Task 6 to also handle `left_p` and `left_m`. Replace `_left_p` / `_left_m` underscores with named usage:

```python
entered_p, left_p, entered_m, left_m = tracker.diff(
    now_participants, now_modules
)
synthetic_seq = self.cursor
now_ts = time.time()
for module_id in sorted(entered_m):
    ...  # existing
for other_id in sorted(entered_p):
    ...  # existing
for module_id in sorted(left_m):
    synthetic_seq += 1
    out.append(
        {
            "type": "proximity_left",
            "seq": synthetic_seq,
            "at": now_ts,
            "left": {"kind": "module", "id": module_id},
            "room_wide": False,
        }
    )
for other_id in sorted(left_p):
    synthetic_seq += 1
    out.append(
        {
            "type": "proximity_left",
            "seq": synthetic_seq,
            "at": now_ts,
            "left": {"kind": "participant", "id": other_id},
            "room_wide": False,
        }
    )
```

- [ ] **Step 4: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_observe_proximity_left.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/world.py backend/tests/test_observe_proximity_left.py
git commit -m "feat(observe): emit proximity_left on exit from radius/rect"
```

---

## Task 8: Agent guide — document proximity, snapshot/leave events, what's always visible

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Test: extend `backend/tests/test_agent_guide_content.py` (created by the 2026-05-20 plan; if not yet present in this branch's HEAD, create it.)

- [ ] **Step 1: Write the failing test additions**

Append to `backend/tests/test_agent_guide_content.py` (or create the file with just these tests if absent):

```python
def test_agent_guide_documents_proximity_radius(client):
    body = client.get("/api/agent-guide").text
    assert "PROXIMITY_RADIUS" in body or "proximity radius" in body.lower()
    assert "180" in body  # the actual value, so agents can tune walks


def test_agent_guide_documents_room_wide_events(client):
    body = client.get("/api/agent-guide").text
    assert "room_wide" in body
    # explicitly name what's always-on
    assert "lighting_changed" in body


def test_agent_guide_documents_proximity_snapshot_and_left(client):
    body = client.get("/api/agent-guide").text
    assert "proximity_snapshot" in body
    assert "proximity_left" in body


def test_agent_guide_documents_walls_out_of_scope(client):
    body = client.get("/api/agent-guide").text
    assert "walls" in body.lower()
    # Make clear that proximity is plain radius, not LOS.
    assert (
        "line-of-sight" in body.lower()
        or "do not block" in body.lower()
        or "ignore walls" in body.lower()
    )
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py -v -k proximity`
Expected: FAIL.

- [ ] **Step 3: Update the agent guide**

In `backend/app/routes/agent_guide.py`, import the constant at the top:

```python
from app.world import PROXIMITY_RADIUS
```

Append a new section to the `_GUIDE` markdown (after the existing "Joining late" section if present, otherwise near the end):

```markdown
## Proximity model

Most events and module state in `/observe` are filtered to what you can
plausibly see/hear from your current `(x, y)`.

- **Radius:** `PROXIMITY_RADIUS = {radius}` world units. (See
  `worldSize` in the room snapshot to gauge scale — `cream-terrazzo` is
  800×500 so the radius is ~36% of the long axis.)
- **Walls do NOT block proximity.** Line-of-sight occlusion is explicitly
  out of scope for v1 — proximity is a plain Euclidean radius. Two
  participants on opposite sides of a wall but within the radius can hear
  each other.

### What `/observe` shows you

When you pass `principal_id` and `principal_kind` as query params (you
should — it's how the server knows where you are):

- `participants` — only those within `PROXIMITY_RADIUS` of you. People
  across the room are OMITTED ENTIRELY (no id, no username). They simply
  don't appear until you walk closer.
- `events` — chats, reactions, moves are only included when the actor
  was within `PROXIMITY_RADIUS` of you AT THE TIME the event fired.
  Module events (`note_created`, `stroke_added`, etc.) are only
  delivered while you are inside that module's `interactionRect`.
- `modules[*]` — the placement info (`x`, `y`, `interactionRect`,
  `approachSlots`) is always present so you can navigate. The live
  state (`notes`, `strokes`, `vote`) is only filled in for modules
  whose `interactionRect` currently contains you.

### Always-visible events (`room_wide: true`)

Some events bypass proximity entirely because they're semantically
room-global. These carry `room_wide: true`:

- `lighting_changed` — the whole room dims/brightens.
- `board_cleared` / `vote_changed` — the drawboard tally is room-visible.

Future event types (broadcasts, music changes) will also set this flag.
When you write code that filters events, treat `room_wide: true` as
"always show this regardless of where I am."

### Walking into earshot: `proximity_snapshot`

When you walk into the radius of another participant OR into a module's
`interactionRect`, the **next** `/observe` poll includes a one-shot
`proximity_snapshot` event:

```
{
  "type": "proximity_snapshot",
  "seq": <int>,
  "at": <ts>,
  "entered": {"kind": "module", "id": "sticky-1"},
  "module": { ...full module snapshot with notes/strokes/vote... },
  "recent_chat": null,
  "room_wide": false
}
```

For participant entry, `module` is `null` and `recent_chat` carries up
to 5 of that participant's most recent chats you hadn't seen yet — so
you can step into a conversation with context.

Snapshot is **one-shot per transition**: poll again without moving and
it won't re-fire.

### Walking out of earshot: `proximity_left`

Inverse: when you walk out of a participant's radius or out of a
module's rect, you get a `proximity_left` event so you can prune local
state:

```
{
  "type": "proximity_left",
  "seq": <int>,
  "at": <ts>,
  "left": {"kind": "participant", "id": "agt_..."},
  "room_wide": false
}
```

```

When formatting the markdown, interpolate the radius value:

```python
_PROXIMITY_BLOCK = _PROXIMITY_BLOCK_TEMPLATE.format(radius=int(PROXIMITY_RADIUS))
```

(or use an f-string when building `_GUIDE`.)

- [ ] **Step 4: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py -v -k proximity`
Expected: PASS.

- [ ] **Step 5: Full suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_content.py
git commit -m "docs(agent-guide): document proximity model, snapshot/left events"
```

---

## Task 9: Frontend types + CLAUDE.md + final verification

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add frontend types**

In `frontend/src/api/types.ts`, add (or extend) the event interfaces:

```ts
// All event types gain an optional room_wide flag (default false).
export interface BaseEvent {
  seq: number;
  at: number;
  room_wide?: boolean;
}

export interface ProximitySnapshotEvent extends BaseEvent {
  type: 'proximity_snapshot';
  entered: { kind: 'module' | 'participant'; id: string };
  module?: ModuleSnapshot | null;
  recent_chat?: ChatEvent[] | null;
}

export interface ProximityLeftEvent extends BaseEvent {
  type: 'proximity_left';
  left: { kind: 'module' | 'participant'; id: string };
}
```

Add to the discriminated union of observe events. Add `room_wide?: boolean` to each existing event interface (additive optional — no consumer breaks).

For the observe response, note in a JSDoc comment that `modules[*].notes` / `strokes` / `vote` may be **absent** when the requester is not in that module's rect.

- [ ] **Step 2: Frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS — purely additive optionals.

- [ ] **Step 3: Full backend suite one more time**

Run: `cd backend && python -m pytest --tb=short`
Expected: ALL PASS.

- [ ] **Step 4: Smoke-test scoped observe manually**

Run: `cd backend && python -m uvicorn app.main:app --port 8902 &`

Then in another shell:
```bash
# Register Alice & Bob, join them at opposite corners, have Bob chat,
# and confirm Alice's scoped observe omits the chat.
curl -s -XPOST localhost:8902/api/sessions -d '{"username":"Alice"}' -H 'content-type: application/json'
# ... (use the principal from the response in the join + observe calls)
```

Kill the server when done. (No commit for this step.)

- [ ] **Step 5: Update CLAUDE.md**

Add a bullet to the "What's Implemented" / Phase notes section:

```
- Proximity-scoped observer (2026-05-26): /observe now scopes participants,
  events, and module state to within PROXIMITY_RADIUS (180 units) of the
  requester. One-shot `proximity_snapshot` on entry, `proximity_left` on
  exit. `room_wide` flag bypasses scoping for lighting / board_cleared /
  vote_changed (and future broadcasts).
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts CLAUDE.md
git commit -m "docs(claude.md,types): note proximity-scoped observer landed"
```

- [ ] **Step 7: Final summary review**

Run: `git log --oneline main..HEAD`
Expected: A clean series of small per-task commits, no fixups.

---

## Self-review checklist

1. **Scope coverage** — every owner addition in §6 (proximity-scoped observe, catch-up snapshot, proximity-leave) and the §4 BUG (notes-at-distance) maps to a task above.
2. **Single source of truth** — `PROXIMITY_RADIUS`, `within_proximity`, `ProximityTracker`, `room_wide`, `proximity_snapshot`, `proximity_left` are all defined exactly once, in this spec, in `backend/app/world.py` / `backend/app/events.py`. Other specs import.
3. **Out-of-scope items called out** — walls / line-of-sight, chat-scope (`room` vs `proximity`), module-scoped chat channel, `actor_color`.
4. **Backwards compatibility** — `/observe` without a principal still returns unscoped data so the existing frontend renderer keeps working until it migrates. The `room_wide` field defaults to `False`, so existing event consumers see only additive optional fields.
5. **Tracker hygiene** — `_proximity_trackers` is cleared on `leave()`. No long-running memory leak beyond unique-joiner count per process lifetime.
6. **One-shot semantics** — `proximity_snapshot` and `proximity_left` are tested both for emission AND for non-repetition on the next poll.
7. **Bug fixed and locked** — `test_notes_hidden_when_requester_not_in_module_rect` reproduces and pins the §4 noteboard-at-distance fix.
