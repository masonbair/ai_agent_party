# Agent API Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land 8 reviewer-found fixes for the agent API on branch `fix/agent-api-review` — server-side wall collision, zone centers in world units, color palette discovery, polling guidance, event ordering, `at` on all events, bearer-token warning, and stable error codes.

**Architecture:** All fixes are additive or contract-stable. Wall collision moves into `backend/app/collision.py` (mirrors the frontend X/Y slide algorithm). Zone centers are derived in `_room_view` for `/observe` only — `GET /api/parties/{slug}` keeps its existing `PartyConfig` shape. Error detail strings become stable machine-readable codes (`principal_unknown`, `not_in_party`). Test-first per task; commit after each.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest + httpx (TestClient), TypeScript/React (frontend touchpoint is one comment).

**Spec:** `docs/superpowers/specs/2026-05-13-agent-api-review-fixes-design.md`

---

## File Map

**Created:**
- `backend/app/collision.py` — `AVATAR_RADIUS`, `inflate_walls`, `slide`.
- `backend/tests/test_collision.py` — unit tests for the pure functions.
- `backend/tests/test_world_collision.py` — `PartyWorld.move()` integration with collision.
- `backend/tests/test_observe_ordering.py` — `/observe` diff is sorted by seq.
- `backend/tests/test_event_at_timestamps.py` — `at` populated on all event types.
- `backend/tests/test_zone_centers.py` — `centerX`/`centerY` in `/observe` room view.
- `backend/tests/test_principal_error_codes.py` — `principal_unknown` and `not_in_party` codes.
- `backend/tests/test_agents_color_palette.py` — 422 detail includes `allowed_colors`.

**Modified:**
- `backend/app/events.py` — add `at: float` to `JoinEvent`, `LeaveEvent`, `MoveEvent`.
- `backend/app/world.py` — precompute inflated rects; `move()` calls `slide()`; populate `at`; sort `observe_since` output by seq.
- `backend/app/routes/party_actions.py` — `_room_view` zones get `centerX`/`centerY`; 409 detail becomes `"not_in_party"`; `observe_since` move dicts include `at`.
- `backend/app/routes/principal.py` — 401 detail becomes `"principal_unknown"`.
- `backend/app/routes/agents.py` — drop `field_validator` for color, validate manually in the route so we can return structured 422 detail.
- `backend/app/routes/agent_guide.py` — rewrite covering colors palette, zone centers, poll cadence, bearer-token warning, recovering-from-errors section.
- `backend/tests/test_observe_route.py` — update zone-keys assertion (now includes `centerX`/`centerY`).
- `backend/tests/test_agent_guide_route.py` — assert new content sections present.
- `frontend/src/hooks/useMovement.ts` — single comment near `AVATAR_RADIUS`.

---

## Conventions

- All `pytest` commands run from repo root unless noted.
- Use existing `client` fixture from `backend/tests/conftest.py`.
- Each task ends with a commit on branch `fix/agent-api-review`.
- Commit message style follows the existing log: `fix(scope): subject` or `feat(scope): subject`.

---

## Task 1: Add `at` timestamps to all event types

Foundation work — other tasks read events expecting `at`.

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/world.py`
- Modify: `backend/app/routes/party_actions.py:148` (observe_since move dict)
- Test: `backend/tests/test_event_at_timestamps.py`

- [ ] **Step 1.1: Write the failing test**

Create `backend/tests/test_event_at_timestamps.py`:

```python
import time

from fastapi.testclient import TestClient


def _human(client: TestClient) -> dict:
    return client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()


def _principal(user: dict) -> dict:
    return {"kind": "human", "id": user["session_id"]}


def test_join_move_chat_events_all_have_at(client: TestClient) -> None:
    user = _human(client)
    before = time.time()
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(user)},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal(user), "x": 200, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal(user), "text": "hi"},
    )
    after = time.time()

    diff = client.get("/api/parties/cream-terrazzo/observe?since=0").json()
    types_with_at = {e["type"]: e["at"] for e in diff["events"]}
    assert {"join", "move", "chat"} <= types_with_at.keys()
    for ts in types_with_at.values():
        assert before - 1.0 <= ts <= after + 1.0
```

- [ ] **Step 1.2: Run test to verify it fails**

```
pytest backend/tests/test_event_at_timestamps.py -v
```

Expected: FAIL — `KeyError: 'at'` on join or move event.

- [ ] **Step 1.3: Add `at` to event models**

Edit `backend/app/events.py`:

```python
from typing import Literal

from pydantic import BaseModel


class Participant(BaseModel):
    id: str
    kind: Literal["human", "agent"]
    username: str
    color: str
    x: float
    y: float
    joined_at: float


class Agent(BaseModel):
    agent_id: str
    username: str
    color: str


class JoinEvent(BaseModel):
    seq: int
    type: Literal["join"] = "join"
    participant: Participant
    at: float


class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"] = "leave"
    participant_id: str
    at: float


class MoveEvent(BaseModel):
    seq: int
    type: Literal["move"] = "move"
    participant_id: str
    x: float
    y: float
    at: float


class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    participant_id: str
    text: str
    at: float


Event = JoinEvent | LeaveEvent | MoveEvent | ChatEvent
```

- [ ] **Step 1.4: Populate `at` in `PartyWorld`**

In `backend/app/world.py`, every event construction now passes `at=time.time()`. Replace the three event-emitting methods:

```python
def join(self, participant: Participant) -> JoinEvent:
    self.participants[participant.id] = participant
    ev = JoinEvent(seq=self._next_seq(), participant=participant, at=time.time())
    self._events.append(ev)
    return ev

def leave(self, participant_id: str) -> LeaveEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    del self.participants[participant_id]
    ev = LeaveEvent(
        seq=self._next_seq(), participant_id=participant_id, at=time.time()
    )
    self._events.append(ev)
    return ev

def move(self, participant_id: str, x: float, y: float) -> MoveEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    w = self._party.worldSize
    cx = _clamp(float(x), 0.0, float(w.width))
    cy = _clamp(float(y), 0.0, float(w.height))
    current = self.participants[participant_id]
    self.participants[participant_id] = current.model_copy(
        update={"x": cx, "y": cy}
    )
    ev = MoveEvent(
        seq=self._next_seq(),
        participant_id=participant_id,
        x=cx,
        y=cy,
        at=time.time(),
    )
    self._events.append(ev)
    return ev
```

(`chat()` already passes `at` — leave it alone.)

- [ ] **Step 1.5: Surface `at` in `observe_since` output dicts**

Still in `backend/app/world.py`, in `observe_since` add `"at": ev.at` to each output dict. Replace the three `out.append(...)` blocks:

```python
if isinstance(ev, JoinEvent):
    out.append(
        {
            "type": "join",
            "seq": ev.seq,
            "at": ev.at,
            "participant": self._participant_dict(ev.participant),
        }
    )
elif isinstance(ev, LeaveEvent):
    out.append(
        {
            "type": "leave",
            "seq": ev.seq,
            "at": ev.at,
            "participant_id": ev.participant_id,
        }
    )
elif isinstance(ev, ChatEvent):
    out.append(
        {
            "type": "chat",
            "seq": ev.seq,
            "at": ev.at,
            "participant_id": ev.participant_id,
            "text": ev.text,
        }
    )
```

And in the trailing move-collapse loop, add `at`:

```python
for pid, mv in latest_move_by_pid.items():
    out.append(
        {
            "type": "move",
            "seq": mv.seq,
            "at": mv.at,
            "participant_id": pid,
            "x": mv.x,
            "y": mv.y,
            "zone": self.derive_zone(mv.x, mv.y),
        }
    )
```

- [ ] **Step 1.6: Run all backend tests to verify nothing else broke**

```
pytest backend/tests -v
```

Expected: PASS (including the new `test_event_at_timestamps.py`).

- [ ] **Step 1.7: Commit**

```
git add backend/app/events.py backend/app/world.py backend/tests/test_event_at_timestamps.py
git commit -m "feat(events): add at timestamp to join/leave/move events"
```

---

## Task 2: Sort `/observe` diff output by seq

The dict-based move-collapse can emit move entries after later chat/leave entries. Sort the output once at the end of `observe_since`.

**Files:**
- Modify: `backend/app/world.py:114-161`
- Test: `backend/tests/test_observe_ordering.py`

- [ ] **Step 2.1: Write the failing test**

Create `backend/tests/test_observe_ordering.py`:

```python
from fastapi.testclient import TestClient


def _human(client: TestClient) -> dict:
    return client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()


def _principal(user: dict) -> dict:
    return {"kind": "human", "id": user["session_id"]}


def test_observe_events_sorted_ascending_by_seq(client: TestClient) -> None:
    user = _human(client)
    cursor = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(user)},
    ).json()["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal(user), "x": 200, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal(user), "text": "hello"},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal(user), "x": 250, "y": 120},
    )

    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]

    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs), f"events not sorted by seq: {seqs}"
```

- [ ] **Step 2.2: Run test to verify it fails**

```
pytest backend/tests/test_observe_ordering.py -v
```

Expected: FAIL — move (latest seq) appears after chat (earlier seq) but with a higher seq, so the order is wrong. (Specifically: chat seq=3, move seq=4 might appear in order [chat, move] — actually that's fine. The real bug appears when there's a chat *after* a series of moves: chat seq=N+1 lands first in `out`, then the collapsed move with seq=N appears last. Confirm by examining the failure carefully.)

If the test happens to pass by accident with this exact sequence, add a fourth action — a chat after the second move — which will reproduce the disorder:

```python
client.post(
    "/api/parties/cream-terrazzo/chat",
    json={"principal": _principal(user), "text": "bye"},
)
```

The collapsed move is emitted after the iteration loop, so it lands at the tail of `out` regardless of seq.

- [ ] **Step 2.3: Sort output before return**

Edit `backend/app/world.py`, the last lines of `observe_since`:

```python
    out.sort(key=lambda e: e["seq"])
    return {"events": out, "cursor": self.cursor}
```

- [ ] **Step 2.4: Run test to verify it passes**

```
pytest backend/tests/test_observe_ordering.py -v
pytest backend/tests -v
```

Expected: PASS on both (all existing tests remain green; ordering is a stricter contract).

- [ ] **Step 2.5: Commit**

```
git add backend/app/world.py backend/tests/test_observe_ordering.py
git commit -m "fix(observe): sort diff events ascending by seq"
```

---

## Task 3: Create `collision.py` with pure functions

Pure-function module first, then integrate into `PartyWorld` in Task 4. Mirrors the algorithm in `frontend/src/hooks/useMovement.ts`.

**Files:**
- Create: `backend/app/collision.py`
- Test: `backend/tests/test_collision.py`

- [ ] **Step 3.1: Write the failing tests**

Create `backend/tests/test_collision.py`:

```python
from app.collision import AVATAR_RADIUS, Rect, inflate_walls, slide
from app.models import Wall, WorldSize


def _walls(*tuples: tuple[float, float, float, float]) -> list[Wall]:
    return [
        Wall(x=x, y=y, width=w, height=h, color="#000")
        for (x, y, w, h) in tuples
    ]


def test_inflate_walls_converts_percent_to_world_units_with_radius() -> None:
    world = WorldSize(width=800, height=500)
    walls = _walls((50.0, 0.0, 0.75, 30.0))
    rects = inflate_walls(walls, world)
    assert len(rects) == 1
    r = rects[0]
    assert r.left == 400.0 - AVATAR_RADIUS
    assert r.right == (50.0 + 0.75) / 100 * 800 + AVATAR_RADIUS
    assert r.top == 0.0 - AVATAR_RADIUS
    assert r.bottom == 150.0 + AVATAR_RADIUS


def test_slide_lets_unblocked_moves_through() -> None:
    rects: list[Rect] = []
    world = WorldSize(width=800, height=500)
    p = slide((100.0, 100.0), (200.0, 200.0), rects, world)
    assert p == (200.0, 200.0)


def test_slide_clamps_to_world_bounds() -> None:
    world = WorldSize(width=800, height=500)
    p = slide((100.0, 100.0), (-50.0, 600.0), [], world)
    assert p == (0.0, 500.0)


def test_slide_blocks_target_in_wall_but_keeps_from_position() -> None:
    # Direct horizontal move into a wall on the same Y as `from`.
    # Wall: inflated x:386-420, y:-14 to 164. From (300,100), to (400,100).
    # Target blocked; X-only also blocked (same point); Y-only is just `from`
    # since to.y == from.y, and (300, 100) is outside the wall -> allowed.
    # Result equals from.
    world = WorldSize(width=800, height=500)
    rects = inflate_walls(_walls((50.0, 0.0, 0.75, 30.0)), world)
    p = slide((300.0, 100.0), (400.0, 100.0), rects, world)
    assert p == (300.0, 100.0)


def test_slide_slides_on_x_axis_when_only_y_is_blocked() -> None:
    # Construct a rect by hand for clarity.
    world = WorldSize(width=800, height=500)
    rects = [Rect(left=200.0, top=50.0, right=400.0, bottom=300.0)]
    # From (150, 150) (outside) to (300, 400) (outside vertically).
    # Target (300, 400): 200<300<400 yes, 50<400<300 no -> not blocked.
    # This isn't actually a slide case. Use a target inside the rect instead:
    p = slide((150.0, 150.0), (300.0, 200.0), rects, world)
    # Target (300, 200): 200<300<400 yes, 50<200<300 yes -> blocked.
    # X-only (300, 150): inside (50<150<300) -> blocked.
    # Y-only (150, 200): 200<150? no -> not in rect -> allowed.
    # Result: (150, 200).
    assert p == (150.0, 200.0)


def test_slide_corner_block_returns_from_position() -> None:
    # Two rects that block both axes from the start point.
    world = WorldSize(width=800, height=500)
    rects = [
        Rect(left=200.0, top=50.0, right=250.0, bottom=300.0),    # vertical bar east of from
        Rect(left=50.0, top=200.0, right=300.0, bottom=250.0),    # horizontal bar south of from
    ]
    # From (150, 150), target (225, 225) is inside the vertical bar.
    # X-only (225, 150): inside vertical bar -> blocked.
    # Y-only (150, 225): inside horizontal bar -> blocked.
    # Corner block -> result equals from.
    p = slide((150.0, 150.0), (225.0, 225.0), rects, world)
    assert p == (150.0, 150.0)
```

- [ ] **Step 3.2: Run tests to verify they fail**

```
pytest backend/tests/test_collision.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.collision'`.

- [ ] **Step 3.3: Implement `collision.py`**

Create `backend/app/collision.py`:

```python
from dataclasses import dataclass

from app.models import Wall, WorldSize

# Avatar treated as a point + walls inflated by this radius.
# Keep in sync with AVATAR_RADIUS in frontend/src/hooks/useMovement.ts.
AVATAR_RADIUS = 14


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float


def inflate_walls(walls: list[Wall], world: WorldSize) -> list[Rect]:
    rects: list[Rect] = []
    for w in walls:
        left = (w.x / 100.0) * world.width - AVATAR_RADIUS
        top = (w.y / 100.0) * world.height - AVATAR_RADIUS
        right = ((w.x + w.width) / 100.0) * world.width + AVATAR_RADIUS
        bottom = ((w.y + w.height) / 100.0) * world.height + AVATAR_RADIUS
        rects.append(Rect(left=left, top=top, right=right, bottom=bottom))
    return rects


def _is_blocked(x: float, y: float, rects: list[Rect]) -> bool:
    for r in rects:
        if r.left < x < r.right and r.top < y < r.bottom:
            return True
    return False


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def slide(
    from_pt: tuple[float, float],
    to_pt: tuple[float, float],
    rects: list[Rect],
    world: WorldSize,
) -> tuple[float, float]:
    """Return the resulting (x, y) after attempting to move from -> to.

    Mirrors the X/Y slide algorithm in frontend useMovement.ts: if the target
    is inside any wall, try the X-only move; if that is blocked, try Y-only;
    if both are blocked, stay put. Then clamp to world bounds.
    """
    fx, fy = from_pt
    tx, ty = to_pt
    nx, ny = tx, ty
    if _is_blocked(nx, ny, rects):
        if not _is_blocked(tx, fy, rects):
            ny = fy
        elif not _is_blocked(fx, ty, rects):
            nx = fx
        else:
            nx, ny = fx, fy
    nx = _clamp(nx, 0.0, float(world.width))
    ny = _clamp(ny, 0.0, float(world.height))
    return (nx, ny)
```

- [ ] **Step 3.4: Run tests to verify they pass**

```
pytest backend/tests/test_collision.py -v
```

Expected: PASS for all six tests.

- [ ] **Step 3.5: Commit**

```
git add backend/app/collision.py backend/tests/test_collision.py
git commit -m "feat(collision): wall inflation and X/Y slide pure functions"
```

---

## Task 4: Integrate collision into `PartyWorld.move()`

**Files:**
- Modify: `backend/app/world.py:23-66`
- Test: `backend/tests/test_world_collision.py`

- [ ] **Step 4.1: Write the failing test**

Create `backend/tests/test_world_collision.py`:

```python
from fastapi.testclient import TestClient


def _human(client: TestClient, username: str = "Alice") -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": "#ff6b9d"}
    ).json()


def _agent(client: TestClient, username: str = "Bot1") -> dict:
    return client.post(
        "/api/agents", json={"username": username, "color": "#4dd0e1"}
    ).json()


def _join_human(client: TestClient, user: dict) -> None:
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": user["session_id"]}, "x": 200, "y": 100},
    )


def _join_agent(client: TestClient, agent: dict) -> None:
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]}, "x": 200, "y": 100},
    )


def test_agent_move_into_wall_is_blocked(client: TestClient) -> None:
    # cream-terrazzo wall: x=50%, y=0-30%, width=0.75%, height=30%.
    # World 800x500 -> wall x:400-406 inflated 386-420; y:0-150 inflated -14 to 164.
    agent = _agent(client)
    _join_agent(client, agent)
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={
            "principal": {"kind": "agent", "id": agent["agent_id"]},
            "x": 400,
            "y": 100,
        },
    )
    assert r.status_code == 200
    body = r.json()
    # X-only (400, 100) still inside the wall; Y-only (200, 100) is fine.
    # So Y-axis slide succeeds with new x=200, y unchanged.
    # Since we asked for x=400, y=100, X is blocked, Y-only at (200, 100) is allowed -> result (200, 100).
    assert (body["x"], body["y"]) == (200.0, 100.0)


def test_human_move_into_wall_is_blocked_same_as_agent(client: TestClient) -> None:
    user = _human(client)
    _join_human(client, user)
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={
            "principal": {"kind": "human", "id": user["session_id"]},
            "x": 400,
            "y": 100,
        },
    )
    body = r.json()
    assert (body["x"], body["y"]) == (200.0, 100.0)


def test_move_clear_of_walls_unchanged(client: TestClient) -> None:
    agent = _agent(client)
    _join_agent(client, agent)
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={
            "principal": {"kind": "agent", "id": agent["agent_id"]},
            "x": 250,
            "y": 250,
        },
    )
    body = r.json()
    assert (body["x"], body["y"]) == (250.0, 250.0)
```

- [ ] **Step 4.2: Run test to verify it fails**

```
pytest backend/tests/test_world_collision.py -v
```

Expected: FAIL — `test_agent_move_into_wall_is_blocked` returns `(400.0, 100.0)` because no collision is enforced server-side.

- [ ] **Step 4.3: Wire collision into `PartyWorld`**

Edit `backend/app/world.py`. Add imports and precompute rects in `__init__`, then replace `move()`:

```python
import time

from app.collision import Rect, inflate_walls, slide
from app.events import (
    ChatEvent,
    Event,
    JoinEvent,
    LeaveEvent,
    MoveEvent,
    Participant,
)
from app.models import PartyConfig
from app.validation import validate_chat_text


class ParticipantNotInPartyError(LookupError):
    pass


class PartyWorld:
    def __init__(self, party: PartyConfig) -> None:
        self._party = party
        self.participants: dict[str, Participant] = {}
        self._events: list[Event] = []
        self._wall_rects: list[Rect] = inflate_walls(
            party.room.walls, party.worldSize
        )
    # ... (rest of class unchanged except move())

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
            participant_id=participant_id,
            x=new_x,
            y=new_y,
            at=time.time(),
        )
        self._events.append(ev)
        return ev
```

The old `_clamp` helper is no longer used (slide does its own clamp). Delete it.

- [ ] **Step 4.4: Run all tests**

```
pytest backend/tests -v
```

Expected: PASS. If any pre-existing test relied on a move into a wall, update it — none should, since the cream-terrazzo wall sits in a narrow strip and existing test coordinates avoid it.

- [ ] **Step 4.5: Commit**

```
git add backend/app/world.py backend/tests/test_world_collision.py
git commit -m "fix(world): enforce wall collision server-side via slide"
```

---

## Task 5: Add `centerX`/`centerY` to `_room_view` zones

Centers are derived in world units. `GET /api/parties/{slug}` is not touched — agents read room layout from `/observe`.

**Files:**
- Modify: `backend/app/routes/party_actions.py:138-162`
- Modify: `backend/tests/test_observe_route.py:21` (zone-keys assertion)
- Test: `backend/tests/test_zone_centers.py`

- [ ] **Step 5.1: Write the failing test**

Create `backend/tests/test_zone_centers.py`:

```python
from fastapi.testclient import TestClient


def test_observe_room_zones_include_world_unit_centers(client: TestClient) -> None:
    body = client.get("/api/parties/cream-terrazzo/observe").json()
    zones = {z["id"]: z for z in body["room"]["zones"]}
    dance = zones["dance"]
    # dance zone: x=6, y=8, width=34, height=36 (percent of 800x500).
    expected_cx = (6.0 + 34.0 / 2) / 100.0 * 800.0  # 184.0
    expected_cy = (8.0 + 36.0 / 2) / 100.0 * 500.0  # 130.0
    assert dance["centerX"] == expected_cx
    assert dance["centerY"] == expected_cy
    # Sanity: posting to centerX/centerY lands in the zone.
    user = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "human", "id": user["session_id"]}
    client.post(
        "/api/parties/cream-terrazzo/join", json={"principal": principal}
    )
    moved = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": principal, "x": dance["centerX"], "y": dance["centerY"]},
    ).json()
    assert moved["zone"] == "dance"
```

- [ ] **Step 5.2: Run test to verify it fails**

```
pytest backend/tests/test_zone_centers.py -v
```

Expected: FAIL — `KeyError: 'centerX'`.

- [ ] **Step 5.3: Update `_room_view` to emit centers**

Edit `backend/app/routes/party_actions.py`, `_room_view`:

```python
def _room_view(party) -> dict:
    w = party.worldSize
    return {
        "slug": party.slug,
        "name": party.name,
        "worldSize": {"width": w.width, "height": w.height},
        "zones": [
            {
                "id": z.id,
                "label": z.label,
                "x": z.x,
                "y": z.y,
                "width": z.width,
                "height": z.height,
                "centerX": (z.x + z.width / 2.0) / 100.0 * w.width,
                "centerY": (z.y + z.height / 2.0) / 100.0 * w.height,
            }
            for z in party.zones
        ],
        "walls": [
            {"x": wl.x, "y": wl.y, "width": wl.width, "height": wl.height}
            for wl in party.room.walls
        ],
        "music": party.music.label,
    }
```

- [ ] **Step 5.4: Update the existing zone-keys assertion**

Edit `backend/tests/test_observe_route.py` line 21:

```python
    assert body["room"]["zones"][0].keys() == {
        "id", "label", "x", "y", "width", "height", "centerX", "centerY",
    }
```

- [ ] **Step 5.5: Run all tests**

```
pytest backend/tests -v
```

Expected: PASS for `test_zone_centers.py` and all existing tests.

- [ ] **Step 5.6: Commit**

```
git add backend/app/routes/party_actions.py backend/tests/test_zone_centers.py backend/tests/test_observe_route.py
git commit -m "feat(observe): expose zone centerX/centerY in world units"
```

---

## Task 6: Stable error codes `principal_unknown` and `not_in_party`

**Files:**
- Modify: `backend/app/routes/principal.py:27,36`
- Modify: `backend/app/routes/party_actions.py:97,112,131`
- Test: `backend/tests/test_principal_error_codes.py`

- [ ] **Step 6.1: Write the failing test**

Create `backend/tests/test_principal_error_codes.py`:

```python
from fastapi.testclient import TestClient


def test_unknown_principal_returns_principal_unknown_code(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={
            "principal": {"kind": "agent", "id": "does-not-exist"},
            "x": 100,
            "y": 100,
        },
    )
    assert r.status_code == 401
    assert r.json() == {"detail": "principal_unknown"}


def test_session_deleted_after_action_returns_principal_unknown(client: TestClient) -> None:
    user = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "human", "id": user["session_id"]}
    client.post(
        "/api/parties/cream-terrazzo/join", json={"principal": principal}
    )
    client.delete(f"/api/session/{user['session_id']}")
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": principal, "x": 100, "y": 100},
    )
    assert r.status_code == 401
    assert r.json() == {"detail": "principal_unknown"}


def test_joined_then_left_returns_not_in_party(client: TestClient) -> None:
    user = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "human", "id": user["session_id"]}
    client.post(
        "/api/parties/cream-terrazzo/join", json={"principal": principal}
    )
    client.post(
        "/api/parties/cream-terrazzo/leave", json={"principal": principal}
    )
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": principal, "x": 100, "y": 100},
    )
    assert r.status_code == 409
    assert r.json() == {"detail": "not_in_party"}
```

- [ ] **Step 6.2: Run tests to verify they fail**

```
pytest backend/tests/test_principal_error_codes.py -v
```

Expected: FAIL — current details are `"invalid principal"` and `"principal not in party"`.

- [ ] **Step 6.3: Update detail strings**

Edit `backend/app/routes/principal.py`:

```python
def resolve_principal(store: Store, principal: Principal) -> ResolvedPrincipal:
    if principal.kind == "human":
        user = store.get_session(principal.id)
        if user is None:
            raise HTTPException(status_code=401, detail="principal_unknown")
        return ResolvedPrincipal(
            id=user.session_id,
            kind="human",
            username=user.username,
            color=user.color,
        )
    agent = store.get_agent(principal.id)
    if agent is None:
        raise HTTPException(status_code=401, detail="principal_unknown")
    return ResolvedPrincipal(
        id=agent.agent_id,
        kind="agent",
        username=agent.username,
        color=agent.color,
    )
```

Edit `backend/app/routes/party_actions.py`, the three `except ParticipantNotInPartyError` blocks (in `leave`, `move`, `chat`) — change each `detail="principal not in party"` to `detail="not_in_party"`.

- [ ] **Step 6.4: Run all tests**

```
pytest backend/tests -v
```

Expected: PASS. Other tests that asserted the old strings need updating — search:

```
grep -rn "principal not in party\|invalid principal" backend/tests/
```

Update any matches to the new codes.

- [ ] **Step 6.5: Commit**

```
git add backend/app/routes/principal.py backend/app/routes/party_actions.py backend/tests/test_principal_error_codes.py
# plus any test files updated for the new codes
git commit -m "fix(api): stable principal_unknown and not_in_party error codes"
```

---

## Task 7: Structured 422 detail for invalid color

Move color validation from the Pydantic `field_validator` (which gives generic 422 detail) into the route handler so we can return a structured detail.

**Files:**
- Modify: `backend/app/routes/agents.py`
- Test: `backend/tests/test_agents_color_palette.py`

- [ ] **Step 7.1: Write the failing test**

Create `backend/tests/test_agents_color_palette.py`:

```python
from fastapi.testclient import TestClient

from app.validation import ALLOWED_COLORS


def test_invalid_color_422_includes_allowed_list(client: TestClient) -> None:
    r = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#000000"}
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_color"
    assert detail["allowed_colors"] == list(ALLOWED_COLORS)


def test_valid_color_still_creates_agent(client: TestClient) -> None:
    r = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    )
    assert r.status_code == 200
    assert r.json()["color"] == "#ff6b9d"
```

- [ ] **Step 7.2: Run test to verify it fails**

```
pytest backend/tests/test_agents_color_palette.py -v
```

Expected: FAIL — current behavior returns Pydantic's generic 422 with `loc`/`msg` structure, not our `invalid_color` shape.

- [ ] **Step 7.3: Move color check into the route**

Edit `backend/app/routes/agents.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator

from app.events import Agent
from app.store import Store
from app.validation import ALLOWED_COLORS, USERNAME_REGEX

router = APIRouter(prefix="/api/agents")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


class CreateAgentRequest(BaseModel):
    username: str
    color: str

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str) -> str:
        if USERNAME_REGEX.fullmatch(v) is None:
            raise ValueError("username must be 2-20 letters/digits")
        return v


@router.post("", response_model=Agent)
def create_agent(
    body: CreateAgentRequest, store: Store = Depends(_store_dep)
) -> Agent:
    if body.color not in ALLOWED_COLORS:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_color",
                "allowed_colors": list(ALLOWED_COLORS),
            },
        )
    return store.register_agent(username=body.username, color=body.color)
```

(The `field_validator` for color is removed; username validator stays. The route is the only entry point so the check is still enforced.)

- [ ] **Step 7.4: Run all tests**

```
pytest backend/tests -v
```

Expected: PASS. If `test_agents_routes.py` asserted the old 422 shape for bad color, update it to expect the new structured detail.

- [ ] **Step 7.5: Commit**

```
git add backend/app/routes/agents.py backend/tests/test_agents_color_palette.py
# plus any pre-existing agent route tests updated
git commit -m "feat(agents): 422 on bad color lists allowed_colors"
```

---

## Task 8: Rewrite `/api/agent-guide`

Document everything from Tasks 1–7. Single rewrite of the `_GUIDE` string.

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Modify: `backend/tests/test_agent_guide_route.py` (add content assertions)

- [ ] **Step 8.1: Write the failing assertions**

Open `backend/tests/test_agent_guide_route.py`. Add tests that assert the new guide content. If the file already has one test verifying basic 200 + markdown, append:

```python
from app.validation import ALLOWED_COLORS


def test_agent_guide_lists_every_allowed_color(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for hex_color in ALLOWED_COLORS:
        assert hex_color in body, f"missing color {hex_color}"


def test_agent_guide_documents_zone_centers(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "centerX" in body
    assert "centerY" in body


def test_agent_guide_documents_poll_cadence(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "1-2" in body or "1–2" in body
    assert "poll" in body.lower()


def test_agent_guide_warns_about_bearer_token(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text.lower()
    assert "password" in body or "bearer" in body


def test_agent_guide_documents_error_codes(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "principal_unknown" in body
    assert "not_in_party" in body
```

If `test_agent_guide_route.py` doesn't exist yet (it does — confirmed via `find`), the imports are:

```python
from fastapi.testclient import TestClient
```

- [ ] **Step 8.2: Run tests to verify they fail**

```
pytest backend/tests/test_agent_guide_route.py -v
```

Expected: FAIL on the new tests — current guide lacks these strings.

- [ ] **Step 8.3: Rewrite the guide**

Replace `_GUIDE` in `backend/app/routes/agent_guide.py`. The literal hex values are interpolated from `ALLOWED_COLORS` at import time so the guide and validator can never drift:

```python
from fastapi import APIRouter, Response

from app.validation import ALLOWED_COLORS

router = APIRouter()


_COLOR_LIST = "\n".join(f"- `{c}`" for c in ALLOWED_COLORS)


_GUIDE = f"""# Agent Guide

You are an AI agent. This document tells you how to participate in a party.

## Register

```
POST /api/agents
{{ "username": "Bot1", "color": "#ff6b9d" }}
```

Response: `{{ "agent_id": "...", "username": "Bot1", "color": "#ff6b9d" }}`.

**Treat `agent_id` like a password.** Anyone who has it can act as your agent. Do not embed it in shared code or logs.

Usernames are 2-20 alphanumeric chars. Allowed colors:

{_COLOR_LIST}

A bad color returns 422 with body `{{ "detail": {{ "error": "invalid_color", "allowed_colors": [...] }} }}`.

## Pick a party

```
GET /api/parties
```

Each party has a `slug` (URL-safe id). Use that slug everywhere below.

## Join

```
POST /api/parties/{{slug}}/join
{{ "principal": {{ "kind": "agent", "id": "<agent_id>" }} }}
```

You appear at the world's center. Optionally pass `x` and `y` to spawn elsewhere.

## The observe loop

First call has no cursor; subsequent calls pass back the `cursor` you last received.

```
GET /api/parties/{{slug}}/observe
GET /api/parties/{{slug}}/observe?since=<cursor>
```

Initial response has `room` (zones, walls, world size, music) and `participants`. Each zone includes `centerX` and `centerY` in **world units** — post these directly to `/move` to walk to that zone's center.

Subsequent responses have only `events` (`join`, `leave`, `move`, `chat`) since your cursor, sorted ascending by `seq`. Every event has an `at` Unix timestamp. Consecutive `move` events from the same participant are collapsed into one entry with the latest position.

**Poll cadence:** every 1-2 seconds. Polling more often does not improve correctness (consecutive moves collapse); it only wastes bandwidth.

## Move

```
POST /api/parties/{{slug}}/move
{{ "principal": {{...}}, "x": 200, "y": 100 }}
```

Coordinates are in world units (see `room.worldSize`). Out-of-bounds values are clamped. Moves into walls are blocked — you'll slide along the unblocked axis or stay put. The response always reports your resulting position: `{{ "x", "y", "zone", "cursor" }}`.

## Chat

```
POST /api/parties/{{slug}}/chat
{{ "principal": {{...}}, "text": "hello everyone" }}
```

Text is limited to 280 chars and characters: letters, digits, spaces, and `.,!?'-`.

## Leave

```
POST /api/parties/{{slug}}/leave
{{ "principal": {{...}} }}
```

Returns 204.

## Recovering from errors

- **401 `{{ "detail": "principal_unknown" }}`** - your `agent_id` is no longer recognized (e.g. server restarted). Re-register with `POST /api/agents` and resume.
- **409 `{{ "detail": "not_in_party" }}`** - you are registered but not in this party (e.g. someone else's `/leave`, or a fresh world). Re-join with `POST /api/parties/{{slug}}/join`.
- **404** on `/api/parties/{{slug}}/*` - the slug is wrong. Re-fetch `GET /api/parties`.

## Example sequence

1. `POST /api/agents` -> save `agent_id`.
2. `GET /api/parties` -> pick a `slug`.
3. `POST /api/parties/{{slug}}/join`.
4. `GET /api/parties/{{slug}}/observe` -> save `cursor`, read the room (note each zone's `centerX`/`centerY`).
5. `POST /api/parties/{{slug}}/move` with `{{ x: zone.centerX, y: zone.centerY }}`.
6. `POST /api/parties/{{slug}}/chat` to greet others.
7. Loop: `GET /api/parties/{{slug}}/observe?since=<cursor>` every 1-2s -> update your model of the world.
8. `POST /api/parties/{{slug}}/leave` when finished.
"""


@router.get("/api/agent-guide")
def agent_guide() -> Response:
    return Response(content=_GUIDE, media_type="text/markdown")
```

Note the doubled `{{` and `}}` — required because the whole string is an f-string and the example JSON contains literal braces.

- [ ] **Step 8.4: Run all tests**

```
pytest backend/tests -v
```

Expected: PASS for all guide tests.

- [ ] **Step 8.5: Commit**

```
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_route.py
git commit -m "docs(agent-guide): colors, centers, cadence, bearer-token, error codes"
```

---

## Task 9: Frontend `AVATAR_RADIUS` cross-pointer comment

Tiny, no behavior change. Keeps the two `AVATAR_RADIUS` constants in sync via grep.

**Files:**
- Modify: `frontend/src/hooks/useMovement.ts:31`

- [ ] **Step 9.1: Add the comment**

Find:

```ts
const AVATAR_RADIUS = 14;
```

Replace with:

```ts
// Keep in sync with AVATAR_RADIUS in backend/app/collision.py.
const AVATAR_RADIUS = 14;
```

- [ ] **Step 9.2: Verify frontend tests still pass**

```
cd frontend && npm test -- --run
```

Expected: PASS (no behavior change).

- [ ] **Step 9.3: Commit**

```
git add frontend/src/hooks/useMovement.ts
git commit -m "chore(frontend): cross-pointer comment for AVATAR_RADIUS"
```

---

## Task 10: Final verification and PR prep

- [ ] **Step 10.1: Run full backend test suite**

```
pytest backend/tests -v
```

Expected: PASS.

- [ ] **Step 10.2: Run full frontend test suite**

```
cd frontend && npm test -- --run
```

Expected: PASS.

- [ ] **Step 10.3: Manual smoke against the running stack**

In one terminal:

```
cd backend && uvicorn app.main:app --reload
```

In another:

```
curl -s http://localhost:8000/api/agent-guide | grep -E "centerX|principal_unknown|password"
```

Expected: each grep line returns text. Also verify `curl http://localhost:8000/api/parties/cream-terrazzo/observe | jq '.room.zones[0]'` shows `centerX` and `centerY` keys.

- [ ] **Step 10.4: Push and open the PR**

```
git push -u origin fix/agent-api-review
gh pr create --title "fix(agent-api): address Phase 3 review findings" --body "..."
```

PR body summarizes the 8 fixes and links the spec.
