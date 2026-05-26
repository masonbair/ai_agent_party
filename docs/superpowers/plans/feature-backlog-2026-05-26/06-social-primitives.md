# Spec #06 — Social Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add follow/unfollow, a generic proposal/vote primitive, a participant lookup endpoint, an `actor_color` field on every event, and an `?exclude_self=true` filter on `/observe` — so agents can express social intent (follow, propose, vote) and maintain a stable id→color map without scraping the initial snapshot.

**Architecture:** All work is server-side in `backend/app/`. `events.py` and `world.py` grow a new `actor_color` field on the unified event base. `world.py` gains follow-graph + proposal-store state and an `_emit_move` helper that auto-syncs followers when their target moves. New routes are split into `backend/app/routes/follow.py` and `backend/app/routes/proposals.py`; the existing `/observe` and a new `GET /participants/{id}` live in `party_actions.py`. Proposals reuse the unified event shape and set `room_wide: true` (a flag introduced by spec #02 on the chat event base — proposals adopt the same convention).

**Tech Stack:** FastAPI (Python 3.11), Pydantic, pytest + httpx (`TestClient`). No new third-party deps.

---

## Spec → Task Map

| Spec § | Task |
|---|---|
| #06.4 `actor_color` on every event payload | Task 2, Task 3 |
| #06.3 `GET /participants/{id}` lookup | Task 4 |
| #06.5 `?exclude_self=true` on `/observe` | Task 5 |
| #06.1 follow/unfollow + auto-move | Tasks 6, 7, 8, 9, 10 |
| #06.2 proposal create / vote / resolve / snapshot | Tasks 11, 12, 13, 14, 15 |
| Agent guide + type sync | Task 16 |

---

## Out of scope (handled by other specs)

- Gesture / cosmetic events (spec #05).
- Module-scoped proposals or sticky-note reactions (spec #04).
- The `room_wide: true` flag itself is defined by spec #02 on the unified event base — this plan uses it but does not introduce it. If spec #02 has not landed when this plan executes, add the field locally on the new proposal events only and document the assumption at the top of Task 11.

---

## File Structure

**Backend — modify:**
- `backend/app/events.py` — add `actor_color: str | None = None` to `JoinEvent.participant` already has it, plus `LeaveEvent`, `MoveEvent`, `ChatEvent`, `ReactionEvent`. Add new `ProposalCreatedEvent`, `ProposalVoteEvent`, `ProposalResolvedEvent`. Extend `Event` union.
- `backend/app/world.py` — populate `actor_color` in `_actor_fields()`. Add follow-graph (`self.followers_of: dict[str, set[str]]`, `self.following: dict[str, str]`). Add proposal store (`self.proposals: dict[str, Proposal]`). Add `_apply_follower_moves(target_id)` helper invoked from `move()`. Add `create_proposal()`, `vote_proposal()`, `resolve_expired_proposals()`. Expose `active_proposals()` for snapshot. Add `PROXIMITY_RADIUS` import (defined by spec #02 — assume present).
- `backend/app/routes/party_actions.py` — handle `?exclude_self=true` on `/observe`; add `GET /participants/{id}` lookup; surface `active_proposals` in the initial snapshot.
- `backend/app/main.py` — mount the new `follow` and `proposals` routers.
- `backend/app/routes/agent_guide.py` — document `actor_color`, follow/unfollow, proposals, `?exclude_self`, participant lookup.
- `backend/app/errors.py` — add error codes: `CANNOT_FOLLOW_SELF`, `TARGET_NOT_IN_PARTY`, `NOT_FOLLOWING`, `PROPOSAL_NOT_FOUND`, `PROPOSAL_EXPIRED`, `INVALID_VOTE`, `INVALID_PROPOSAL_TEXT`, `INVALID_EXPIRY`.
- `frontend/src/api/types.ts` — add `actor_color?` to event types; add `Proposal`, follow request/response, participant lookup response.

**Backend — create:**
- `backend/app/routes/follow.py` — `POST /api/parties/{slug}/follow`, `POST /api/parties/{slug}/unfollow`.
- `backend/app/routes/proposals.py` — `POST /api/parties/{slug}/proposals`, `POST /api/parties/{slug}/proposals/{id}/vote`.

**Backend — new tests:**
- `backend/tests/test_event_actor_color.py`
- `backend/tests/test_observe_exclude_self.py`
- `backend/tests/test_participant_lookup_route.py`
- `backend/tests/test_follow_route.py`
- `backend/tests/test_follow_auto_move.py`
- `backend/tests/test_proposals_route.py`
- `backend/tests/test_proposals_resolve.py`
- `backend/tests/test_observe_active_proposals.py`

---

## Task 1: Pre-flight — confirm baseline

**Files:** none (read-only)

- [ ] **Step 1: Run backend tests**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 2: Confirm spec #01 and #02 dependencies present**

Run: `grep -n "PROXIMITY_RADIUS" backend/app/world.py && grep -n "room_wide" backend/app/events.py`
Expected: both grep commands print at least one line. If either is missing, STOP and note that this plan depends on specs #01/#02 having merged. As a fallback for `PROXIMITY_RADIUS`, define it as a top-level constant `PROXIMITY_RADIUS = 180.0` in `backend/app/world.py` in Task 7 and call out the temporary value in the commit message.

- [ ] **Step 3: Do not commit — baseline only**

---

## Task 2: Add `actor_color` to unified event models

**Files:**
- Modify: `backend/app/events.py`
- Test: `backend/tests/test_event_actor_color.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_event_actor_color.py`:

```python
"""Every event with actor_* fields must also carry actor_color."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _principal(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_move_event_includes_actor_color(client: TestClient) -> None:
    a = _agent(client, "Mover", "#4dd0e1")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(a)},
    )
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal(a), "x": 200, "y": 200},
    )
    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]
    moves = [e for e in events if e["type"] == "move"]
    assert moves, "expected at least one move event"
    assert moves[0]["actor_color"] == "#4dd0e1"


def test_chat_event_includes_actor_color(client: TestClient) -> None:
    a = _agent(client, "Talker", "#ff6b9d")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(a)},
    )
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal(a), "text": "hello"},
    )
    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]
    chats = [e for e in events if e["type"] == "chat"]
    assert chats
    assert chats[0]["actor_color"] == "#ff6b9d"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_event_actor_color.py -v`
Expected: FAIL — `actor_color` key missing on event dicts.

- [ ] **Step 3: Add `actor_color` field to event models**

Edit `backend/app/events.py`. For each of `LeaveEvent`, `MoveEvent`, `ChatEvent`, `ReactionEvent`, add the line `actor_color: str | None = None` immediately below the existing `actor_kind:` line. Example for `MoveEvent`:

```python
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
    actor_color: str | None = None
```

Repeat exactly the same `actor_color: str | None = None` line addition for `LeaveEvent`, `ChatEvent`, and `ReactionEvent`. `JoinEvent` already exposes color via `participant.color` — do not duplicate.

- [ ] **Step 4: Run tests — still failing because world doesn't populate it yet**

Run: `cd backend && python -m pytest tests/test_event_actor_color.py -v`
Expected: FAIL — `actor_color` is `None` in the response.

- [ ] **Step 5: Commit the schema-only change**

```bash
git add backend/app/events.py backend/tests/test_event_actor_color.py
git commit -m "feat(events): add actor_color field to unified event base"
```

---

## Task 3: Populate `actor_color` in world

**Files:**
- Modify: `backend/app/world.py:139-148`

- [ ] **Step 1: Edit `_actor_fields` to include color**

Replace the `_actor_fields` method body in `backend/app/world.py` (lines 139–148) with:

```python
    def _actor_fields(self, participant_id: str) -> dict:
        p = self.participants.get(participant_id)
        if p is None:
            return {}
        return {
            "actor_id": p.id,
            "actor_username": p.username,
            "actor_kind": p.kind,
            "actor_color": p.color,
        }
```

- [ ] **Step 2: Run the actor_color tests — expect pass**

Run: `cd backend && python -m pytest tests/test_event_actor_color.py -v`
Expected: PASS.

- [ ] **Step 3: Run the full backend suite to catch regressions**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS. If `test_event_actor_fields.py` asserts the exact set of actor_* keys, update it to include `actor_color` in the assertion.

- [ ] **Step 4: Commit**

```bash
git add backend/app/world.py
git commit -m "feat(world): populate actor_color on every actor event"
```

---

## Task 4: `GET /participants/{id}` lookup endpoint

**Files:**
- Modify: `backend/app/routes/party_actions.py`
- Test: `backend/tests/test_participant_lookup_route.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_participant_lookup_route.py`:

```python
"""Direct participant lookup — bypasses proximity scoping for id resolution."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _principal(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_lookup_returns_participant_fields(client: TestClient) -> None:
    a = _agent(client, "Lookee", "#ff6b9d")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(a), "x": 123.0, "y": 234.0},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/participants/{a['agent_id']}"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == a["agent_id"]
    assert body["username"] == "Lookee"
    assert body["color"] == "#ff6b9d"
    assert body["kind"] == "agent"
    assert body["x"] == 123.0
    assert body["y"] == 234.0
    assert "zone" in body
    assert "facing" in body


def test_lookup_404_when_not_in_party(client: TestClient) -> None:
    r = client.get(
        "/api/parties/cream-terrazzo/participants/no-such-id"
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "not_in_party"


def test_lookup_404_when_party_missing(client: TestClient) -> None:
    r = client.get("/api/parties/no-such-party/participants/whatever")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd backend && python -m pytest tests/test_participant_lookup_route.py -v`
Expected: FAIL — route not defined.

- [ ] **Step 3: Implement the endpoint**

Add the following route function to `backend/app/routes/party_actions.py` immediately before the `_room_view` function:

```python
@router.get("/{slug}/participants/{participant_id}")
def get_participant(
    slug: str = Path(pattern=_SLUG_PATTERN),
    participant_id: str = Path(...),
    store: Store = Depends(_store_dep),
) -> dict:
    """Resolve a participant by id, bypassing proximity scoping.

    This is for username→id resolution (e.g. so an agent can rebuild a
    stale color map without rejoining). It is NOT an eavesdrop channel:
    it returns only the same public fields already visible in the
    proximity-scoped snapshot whenever the requester sees the target.
    """
    world = _world(store, slug)
    p = world.participants.get(participant_id)
    if p is None:
        raise HTTPException(
            status_code=404, detail=envelope(NOT_IN_PARTY),
        )
    return {
        "id": p.id,
        "username": p.username,
        "color": p.color,
        "kind": p.kind,
        "x": p.x,
        "y": p.y,
        "zone": world.derive_zone(p.x, p.y),
        "facing": getattr(p, "facing", None),
    }
```

Ensure these imports exist near the top of the file (add any missing ones):

```python
from app.errors import INVALID_CHAT_TEXT, NOT_IN_PARTY, envelope
```

- [ ] **Step 4: Run tests — expect pass**

Run: `cd backend && python -m pytest tests/test_participant_lookup_route.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/party_actions.py backend/tests/test_participant_lookup_route.py
git commit -m "feat(party): GET /participants/{id} for id resolution"
```

---

## Task 5: `?exclude_self=true` on `/observe`

**Files:**
- Modify: `backend/app/routes/party_actions.py` (the `observe` function)
- Test: `backend/tests/test_observe_exclude_self.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_observe_exclude_self.py`:

```python
"""?exclude_self=true filters out events whose actor_id == requester."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_exclude_self_drops_own_chat_events(client: TestClient) -> None:
    a = _agent(client, "Self", "#4dd0e1")
    b = _agent(client, "Other", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _p(a), "text": "from a"},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _p(b), "text": "from b"},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/observe"
        f"?since={cursor}&exclude_self=true"
        f"&principal_kind=agent&principal_id={a['agent_id']}"
    )
    events = r.json()["events"]
    chats = [e for e in events if e["type"] == "chat"]
    assert all(e.get("actor_id") != a["agent_id"] for e in chats)
    assert any(e.get("actor_id") == b["agent_id"] for e in chats)


def test_exclude_self_default_off(client: TestClient) -> None:
    a = _agent(client, "Self", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _p(a), "text": "hi"},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    )
    chats = [e for e in r.json()["events"] if e["type"] == "chat"]
    assert any(e.get("actor_id") == a["agent_id"] for e in chats)
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd backend && python -m pytest tests/test_observe_exclude_self.py -v`
Expected: FAIL — extra query params ignored.

- [ ] **Step 3: Extend the `/observe` route**

Replace the `observe` function in `backend/app/routes/party_actions.py` (the `@router.get("/{slug}/observe")` handler) with:

```python
@router.get("/{slug}/observe")
def observe(
    slug: str = Path(pattern=_SLUG_PATTERN),
    since: int | None = None,
    exclude_self: bool = False,
    principal_kind: str | None = None,
    principal_id: str | None = None,
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    party = store.get_party(slug)
    assert party is not None
    if since is None:
        snap = world.snapshot()
        return {
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
            "modules": snap["modules"],
            "lighting": snap["lighting"],
            "active_reactions": snap["active_reactions"],
            "recent_chat": world.recent_chat(),
            "active_proposals": world.active_proposals(),
        }
    payload = world.observe_since(since)
    if exclude_self and principal_id:
        payload["events"] = [
            e for e in payload["events"]
            if e.get("actor_id") != principal_id
        ]
    return payload
```

Note: `active_proposals()` is added in Task 11. If running tests before Task 11 is complete, temporarily change `world.active_proposals()` to `[]` and revert in Task 11. The test in this task does not exercise active_proposals.

- [ ] **Step 4: Run tests — expect pass**

Run: `cd backend && python -m pytest tests/test_observe_exclude_self.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/party_actions.py backend/tests/test_observe_exclude_self.py
git commit -m "feat(observe): support ?exclude_self=true filter"
```

---

## Task 6: Follow graph state on `PartyWorld`

**Files:**
- Modify: `backend/app/world.py` (`__init__`)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_follow_route.py` with the route shell (we'll extend it in Task 8):

```python
"""POST /follow records follower→target on the world."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_follow_stores_relationship(client: TestClient) -> None:
    a = _agent(client, "Follower", "#4dd0e1")
    b = _agent(client, "Target", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    r = client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    assert r.status_code == 200
    assert r.json()["target_id"] == b["agent_id"]
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd backend && python -m pytest tests/test_follow_route.py -v`
Expected: FAIL — route not defined.

- [ ] **Step 3: Add follow-graph state to `PartyWorld.__init__`**

In `backend/app/world.py`, inside `PartyWorld.__init__`, just after the line `self.active_reactions: dict[str, Reaction] = {}`, add:

```python
        # follow graph: follower_id -> target_id (one target per follower)
        self.following: dict[str, str] = {}
        # reverse index: target_id -> set of follower ids
        self.followers_of: dict[str, set[str]] = {}
        # proposals (Task 11 fills out shape)
        self.proposals: dict[str, dict] = {}
```

- [ ] **Step 4: Commit (route comes next)**

```bash
git add backend/app/world.py
git commit -m "feat(world): scaffold follow graph + proposal store state"
```

---

## Task 7: `world.follow()` / `world.unfollow()` + auto-clear on leave

**Files:**
- Modify: `backend/app/world.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_follow_auto_move.py`:

```python
"""When a followed target moves, the follower auto-moves toward them
   and stops at PROXIMITY_RADIUS - 20 distance."""

import math

from fastapi.testclient import TestClient

from app.world import PROXIMITY_RADIUS


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_follower_auto_moves_when_target_moves(client: TestClient) -> None:
    a = _agent(client, "Follower", "#4dd0e1")
    b = _agent(client, "Target", "#ff6b9d")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(a), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(b), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _p(b), "x": 600, "y": 400},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/participants/{a['agent_id']}"
    ).json()
    dx, dy = 600 - r["x"], 400 - r["y"]
    dist = math.hypot(dx, dy)
    expected = PROXIMITY_RADIUS - 20
    assert abs(dist - expected) < 1.0, (
        f"follower should be {expected} units from target, got {dist}"
    )


def test_follow_auto_clears_on_target_leave(client: TestClient) -> None:
    a = _agent(client, "Follower", "#4dd0e1")
    b = _agent(client, "Target", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    client.post("/api/parties/cream-terrazzo/leave", json={"principal": _p(b)})
    # Re-join b; following should NOT resume.
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _p(b), "x": 700, "y": 400},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/participants/{a['agent_id']}"
    ).json()
    # Follower should be at its original spawn (world center 400,250), not
    # near (700,400).
    assert (r["x"], r["y"]) == (400.0, 250.0)
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd backend && python -m pytest tests/test_follow_auto_move.py -v`
Expected: FAIL — `world.follow` and `/follow` route missing.

- [ ] **Step 3: Add `follow` / `unfollow` methods and the auto-move side effect**

Add the following methods to `PartyWorld` in `backend/app/world.py` (just below the `leave()` method). Also add a constant near the top if spec #02 hasn't provided one — see Task 1 Step 2 fallback.

```python
    class CannotFollowSelfError(ValueError):
        pass

    class TargetNotInPartyError(LookupError):
        pass

    def follow(self, follower_id: str, target_id: str) -> None:
        if follower_id not in self.participants:
            raise ParticipantNotInPartyError(follower_id)
        if follower_id == target_id:
            raise PartyWorld.CannotFollowSelfError(follower_id)
        if target_id not in self.participants:
            raise PartyWorld.TargetNotInPartyError(target_id)
        # Clear any prior follow target.
        prev = self.following.get(follower_id)
        if prev is not None:
            self.followers_of.get(prev, set()).discard(follower_id)
        self.following[follower_id] = target_id
        self.followers_of.setdefault(target_id, set()).add(follower_id)

    def unfollow(self, follower_id: str) -> None:
        if follower_id not in self.participants:
            raise ParticipantNotInPartyError(follower_id)
        prev = self.following.pop(follower_id, None)
        if prev is not None:
            self.followers_of.get(prev, set()).discard(follower_id)

    def _clear_follow_links_for(self, participant_id: str) -> None:
        """Called on leave: removes the participant from both sides."""
        prev = self.following.pop(participant_id, None)
        if prev is not None:
            self.followers_of.get(prev, set()).discard(participant_id)
        followers = self.followers_of.pop(participant_id, set())
        for f in followers:
            self.following.pop(f, None)
```

- [ ] **Step 4: Wire `leave()` to clear follow links**

In `backend/app/world.py`, the existing `leave()` method (around line 157) — replace its body so the cleanup runs after the participant is removed but before the event is emitted. Replace:

```python
    def leave(self, participant_id: str) -> LeaveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        actor = self._actor_fields(participant_id)
        del self.participants[participant_id]
        ev = LeaveEvent(
            seq=self._next_seq(),
            participant_id=participant_id,
            at=time.time(),
            **actor,
        )
        self._events.append(ev)
        self._emit(ev)
        self._recompute_all_drawboard_votes(time.time())
        return ev
```

with:

```python
    def leave(self, participant_id: str) -> LeaveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        actor = self._actor_fields(participant_id)
        self._clear_follow_links_for(participant_id)
        del self.participants[participant_id]
        ev = LeaveEvent(
            seq=self._next_seq(),
            participant_id=participant_id,
            at=time.time(),
            **actor,
        )
        self._events.append(ev)
        self._emit(ev)
        self._recompute_all_drawboard_votes(time.time())
        return ev
```

- [ ] **Step 5: Implement follower auto-move in `move()`**

Edit `backend/app/world.py` `move()` method. After the `self._emit(ev)` line and before `self._recompute_all_drawboard_votes(...)`, insert:

```python
        # Auto-move any followers of the participant who just moved.
        self._apply_follower_moves(participant_id)
```

Then add a new method right below `move()`:

```python
    def _apply_follower_moves(self, target_id: str) -> None:
        import math
        followers = list(self.followers_of.get(target_id, set()))
        if not followers:
            return
        target = self.participants.get(target_id)
        if target is None:
            return
        stop_distance = PROXIMITY_RADIUS - 20.0
        for fid in followers:
            f = self.participants.get(fid)
            if f is None:
                continue
            dx, dy = target.x - f.x, target.y - f.y
            dist = math.hypot(dx, dy)
            if dist <= stop_distance or dist == 0:
                continue
            scale = (dist - stop_distance) / dist
            new_x = f.x + dx * scale
            new_y = f.y + dy * scale
            # Reuse normal move pipeline so collision + zone + actor fields apply.
            self._move_internal(fid, new_x, new_y)

    def _move_internal(self, participant_id: str, x: float, y: float) -> MoveEvent:
        """Internal move that emits a normal move event but skips recursive
        follower processing for the actor itself (it can still trigger their
        followers, but we don't infinite-loop on the original target)."""
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
            **self._actor_fields(participant_id),
        )
        self._events.append(ev)
        self._emit(ev)
        return ev
```

Confirm `PROXIMITY_RADIUS` is importable at module scope. If not, add this near the top of `world.py`:

```python
PROXIMITY_RADIUS = 180.0  # owned by spec #02 — temporary fallback
```

- [ ] **Step 6: Run the auto-move test — still fails (route not yet present)**

Run: `cd backend && python -m pytest tests/test_follow_auto_move.py -v`
Expected: FAIL — `/follow` route still returns 404. We add that in Task 8.

- [ ] **Step 7: Commit**

```bash
git add backend/app/world.py
git commit -m "feat(world): follow/unfollow + follower auto-move on target move"
```

---

## Task 8: `/follow` and `/unfollow` routes

**Files:**
- Create: `backend/app/routes/follow.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/errors.py`

- [ ] **Step 1: Add error codes**

Edit `backend/app/errors.py`. Append below `DM_FORBIDDEN`:

```python
CANNOT_FOLLOW_SELF = "cannot_follow_self"
TARGET_NOT_IN_PARTY = "target_not_in_party"
NOT_FOLLOWING = "not_following"
PROPOSAL_NOT_FOUND = "proposal_not_found"
PROPOSAL_EXPIRED = "proposal_expired"
INVALID_VOTE = "invalid_vote"
INVALID_PROPOSAL_TEXT = "invalid_proposal_text"
INVALID_EXPIRY = "invalid_expiry"
```

- [ ] **Step 2: Create `follow.py`**

Create `backend/app/routes/follow.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel

from app.errors import (
    CANNOT_FOLLOW_SELF,
    NOT_IN_PARTY,
    TARGET_NOT_IN_PARTY,
    envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")

_SLUG_PATTERN = r"^[a-z0-9-]+$"


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    w = store.get_or_create_world(slug)
    if w is None:
        raise HTTPException(status_code=404, detail="party not found")
    return w


class FollowRequest(BaseModel):
    principal: Principal
    target_id: str


class UnfollowRequest(BaseModel):
    principal: Principal


@router.post("/{slug}/follow")
def follow(
    body: FollowRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.follow(resolved.id, body.target_id)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    except PartyWorld.CannotFollowSelfError:
        raise HTTPException(
            status_code=400, detail=envelope(CANNOT_FOLLOW_SELF)
        )
    except PartyWorld.TargetNotInPartyError:
        raise HTTPException(
            status_code=404, detail=envelope(TARGET_NOT_IN_PARTY)
        )
    return {"target_id": body.target_id}


@router.post("/{slug}/unfollow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow(
    body: UnfollowRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> Response:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.unfollow(resolved.id)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 3: Mount the router in `main.py`**

Open `backend/app/main.py`. Add `from app.routes import follow as follow_routes` near the other route imports, and add `app.include_router(follow_routes.router)` next to the other `include_router` calls.

- [ ] **Step 4: Add dependency override in `conftest.py`**

Edit `backend/tests/conftest.py`. Add to the imports: `from app.routes import follow as follow_routes`. In the `client` fixture, add `app.dependency_overrides[follow_routes._store_dep] = lambda: store` alongside the other overrides.

- [ ] **Step 5: Add follow self/target-not-in-party error tests**

Append to `backend/tests/test_follow_route.py`:

```python
def test_follow_self_returns_400(client: TestClient) -> None:
    a = _agent(client, "Solo", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": a["agent_id"]},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "cannot_follow_self"


def test_follow_unknown_target_returns_404(client: TestClient) -> None:
    a = _agent(client, "F", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": "nope"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "target_not_in_party"


def test_unfollow_clears(client: TestClient) -> None:
    a = _agent(client, "F", "#4dd0e1")
    b = _agent(client, "T", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/unfollow",
        json={"principal": _p(a)},
    )
    assert r.status_code == 204
```

- [ ] **Step 6: Run all follow tests**

Run: `cd backend && python -m pytest tests/test_follow_route.py tests/test_follow_auto_move.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/follow.py backend/app/main.py backend/app/errors.py backend/tests/test_follow_route.py backend/tests/conftest.py
git commit -m "feat(follow): POST /follow and /unfollow endpoints"
```

---

## Task 9: Follower auto-clear on follower-leave (regression test)

**Files:**
- Test: `backend/tests/test_follow_route.py` (extend)

- [ ] **Step 1: Append failing test**

Append to `backend/tests/test_follow_route.py`:

```python
def test_follow_auto_clears_on_follower_leave(client: TestClient) -> None:
    a = _agent(client, "F", "#4dd0e1")
    b = _agent(client, "T", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    client.post("/api/parties/cream-terrazzo/leave", json={"principal": _p(a)})
    # Re-join a at fixed pos; verify b moving does NOT auto-pull a.
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(a), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _p(b), "x": 700, "y": 400},
    )
    r = client.get(
        f"/api/parties/cream-terrazzo/participants/{a['agent_id']}"
    ).json()
    assert (r["x"], r["y"]) == (100.0, 100.0)
```

- [ ] **Step 2: Run — should already pass (Task 7 added `_clear_follow_links_for` in `leave()`)**

Run: `cd backend && python -m pytest tests/test_follow_route.py::test_follow_auto_clears_on_follower_leave -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_follow_route.py
git commit -m "test(follow): cover follower-leave auto-clear"
```

---

## Task 10: Follower auto-move emits proximity-scoped (NOT room_wide) move event

**Files:**
- Test: `backend/tests/test_follow_auto_move.py` (extend)

- [ ] **Step 1: Append test**

```python
def test_follower_auto_move_emits_normal_move_event(client: TestClient) -> None:
    a = _agent(client, "F", "#4dd0e1")
    b = _agent(client, "T", "#ff6b9d")
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(a), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _p(b), "x": 100, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/follow",
        json={"principal": _p(a), "target_id": b["agent_id"]},
    )
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _p(b), "x": 600, "y": 400},
    )
    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]
    follower_moves = [
        e for e in events
        if e["type"] == "move" and e["actor_id"] == a["agent_id"]
    ]
    assert follower_moves, "expected a synthetic move for the follower"
    # Auto-moves must not be tagged room_wide (proximity-scoped like normal).
    for e in follower_moves:
        assert e.get("room_wide", False) is False
```

- [ ] **Step 2: Run — expect pass (the existing `_move_internal` uses MoveEvent with default room_wide)**

Run: `cd backend && python -m pytest tests/test_follow_auto_move.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_follow_auto_move.py
git commit -m "test(follow): assert follower auto-move emits proximity-scoped move"
```

---

## Task 11: Generic `POST /proposals` endpoint

**Files:**
- Create: `backend/app/routes/proposals.py`
- Modify: `backend/app/world.py` (add `create_proposal`, `active_proposals`, proposal events)
- Modify: `backend/app/events.py` (add proposal event types)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_proposals_route.py`

> Assumption (carry from Task 1 Step 2): spec #02 defines `room_wide: bool = False` on the chat event base. Proposal events set `room_wide: True`. If absent, add `room_wide: bool = True` directly on the three new proposal event models.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_proposals_route.py`:

```python
"""POST /proposals creates a proposal; POST /proposals/{id}/vote tallies."""

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_create_proposal_returns_id_and_expiry(client: TestClient) -> None:
    a = _agent(client, "Proposer", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "lets dance", "expires_in_sec": 10},
    )
    assert r.status_code == 200
    body = r.json()
    assert "proposal_id" in body
    assert isinstance(body["expires_at"], float)


def test_proposal_created_event_is_room_wide(client: TestClient) -> None:
    a = _agent(client, "P", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "go home", "expires_in_sec": 5},
    )
    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]
    created = [e for e in events if e["type"] == "proposal_created"]
    assert created
    assert created[0]["room_wide"] is True
    assert created[0]["text"] == "go home"
    assert created[0]["actor_id"] == a["agent_id"]


def test_create_proposal_invalid_expiry(client: TestClient) -> None:
    a = _agent(client, "P", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "hi", "expires_in_sec": 0},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_expiry"

    r2 = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "hi", "expires_in_sec": 999},
    )
    assert r2.status_code == 422
    assert r2.json()["detail"]["error"] == "invalid_expiry"


def test_create_proposal_invalid_text(client: TestClient) -> None:
    a = _agent(client, "P", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "", "expires_in_sec": 5},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_proposal_text"
```

- [ ] **Step 2: Run — fails (route + events missing)**

Run: `cd backend && python -m pytest tests/test_proposals_route.py -v`
Expected: FAIL.

- [ ] **Step 3: Add proposal event types**

Append to `backend/app/events.py` (before the `Event = ...` union):

```python
class ProposalCreatedEvent(BaseModel):
    seq: int
    type: Literal["proposal_created"] = "proposal_created"
    proposal_id: str
    text: str
    expires_at: float
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    actor_color: str | None = None
    room_wide: bool = True


class ProposalVoteEvent(BaseModel):
    seq: int
    type: Literal["proposal_vote"] = "proposal_vote"
    proposal_id: str
    vote: Literal["yes", "no", "abstain"]
    tallies: dict  # {"yes": int, "no": int, "abstain": int}
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    actor_color: str | None = None
    room_wide: bool = True


class ProposalResolvedEvent(BaseModel):
    seq: int
    type: Literal["proposal_resolved"] = "proposal_resolved"
    proposal_id: str
    text: str
    tallies: dict
    at: float
    room_wide: bool = True
```

Extend the `Event` union to include the three new types:

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
    | ProposalCreatedEvent
    | ProposalVoteEvent
    | ProposalResolvedEvent
)
```

- [ ] **Step 4: Add `create_proposal` + `active_proposals` to `PartyWorld`**

Add imports at top of `backend/app/world.py`:

```python
from app.events import (
    ProposalCreatedEvent,
    ProposalResolvedEvent,
    ProposalVoteEvent,
)
```

Add a small validation helper near the top of `world.py` (or in `validation.py` if you prefer — keeping here for proximity):

```python
PROPOSAL_TEXT_MAX = 65  # mirrors chat cap (shared brief: do not raise)
```

Add methods to `PartyWorld`:

```python
    def create_proposal(
        self, participant_id: str, text: str, expires_in_sec: int
    ) -> ProposalCreatedEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        if not (1 <= int(expires_in_sec) <= 60):
            raise ValueError("invalid_expiry")
        # Reuse chat validation (regex + char cap) per spec #03 updates.
        cleaned = validate_chat_text(text)
        if len(cleaned) == 0 or len(cleaned) > PROPOSAL_TEXT_MAX:
            raise ValueError("invalid_proposal_text")
        now = time.time()
        pid = uuid.uuid4().hex
        expires_at = now + float(expires_in_sec)
        self.proposals[pid] = {
            "id": pid,
            "text": cleaned,
            "expires_at": expires_at,
            "created_by": participant_id,
            "votes": {},  # participant_id -> "yes"|"no"|"abstain"
            "resolved": False,
        }
        ev = ProposalCreatedEvent(
            seq=self._next_seq(),
            proposal_id=pid,
            text=cleaned,
            expires_at=expires_at,
            at=now,
            **self._actor_fields(participant_id),
        )
        self._events.append(ev)
        self._emit(ev)
        return ev

    def _tally(self, proposal_id: str) -> dict:
        votes = self.proposals[proposal_id]["votes"]
        out = {"yes": 0, "no": 0, "abstain": 0}
        for v in votes.values():
            if v in out:
                out[v] += 1
        return out

    def vote_proposal(
        self, participant_id: str, proposal_id: str, vote: str
    ) -> ProposalVoteEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        p = self.proposals.get(proposal_id)
        if p is None or p["resolved"]:
            raise KeyError(proposal_id)
        now = time.time()
        if now >= p["expires_at"]:
            raise TimeoutError(proposal_id)
        if vote not in ("yes", "no", "abstain"):
            raise ValueError("invalid_vote")
        p["votes"][participant_id] = vote
        tallies = self._tally(proposal_id)
        ev = ProposalVoteEvent(
            seq=self._next_seq(),
            proposal_id=proposal_id,
            vote=vote,
            tallies=tallies,
            at=now,
            **self._actor_fields(participant_id),
        )
        self._events.append(ev)
        self._emit(ev)
        return ev

    def resolve_expired_proposals(self) -> list[ProposalResolvedEvent]:
        now = time.time()
        out: list[ProposalResolvedEvent] = []
        for pid, p in list(self.proposals.items()):
            if p["resolved"]:
                continue
            if now >= p["expires_at"]:
                p["resolved"] = True
                ev = ProposalResolvedEvent(
                    seq=self._next_seq(),
                    proposal_id=pid,
                    text=p["text"],
                    tallies=self._tally(pid),
                    at=now,
                )
                self._events.append(ev)
                self._emit(ev)
                out.append(ev)
        return out

    def active_proposals(self) -> list[dict]:
        # Lazy resolution: anything past expiry is resolved on next read.
        self.resolve_expired_proposals()
        return [
            {
                "id": p["id"],
                "text": p["text"],
                "expires_at": p["expires_at"],
                "created_by": p["created_by"],
                "tallies": self._tally(p["id"]),
            }
            for p in self.proposals.values()
            if not p["resolved"]
        ]
```

- [ ] **Step 5: Create the route file**

Create `backend/app/routes/proposals.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import (
    INVALID_EXPIRY,
    INVALID_PROPOSAL_TEXT,
    INVALID_VOTE,
    NOT_IN_PARTY,
    PROPOSAL_EXPIRED,
    PROPOSAL_NOT_FOUND,
    envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import ChatValidationError
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")

_SLUG_PATTERN = r"^[a-z0-9-]+$"


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    w = store.get_or_create_world(slug)
    if w is None:
        raise HTTPException(status_code=404, detail="party not found")
    return w


class CreateProposalRequest(BaseModel):
    principal: Principal
    text: str
    expires_in_sec: int


class VoteRequest(BaseModel):
    principal: Principal
    vote: str


@router.post("/{slug}/proposals")
def create_proposal(
    body: CreateProposalRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.create_proposal(resolved.id, body.text, body.expires_in_sec)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(INVALID_PROPOSAL_TEXT, message=str(exc)),
        )
    except ValueError as exc:
        msg = str(exc)
        if msg == "invalid_expiry":
            raise HTTPException(status_code=422, detail=envelope(INVALID_EXPIRY))
        raise HTTPException(
            status_code=422, detail=envelope(INVALID_PROPOSAL_TEXT)
        )
    return {"proposal_id": ev.proposal_id, "expires_at": ev.expires_at}


@router.post("/{slug}/proposals/{proposal_id}/vote")
def vote_proposal(
    body: VoteRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    proposal_id: str = Path(...),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.vote_proposal(resolved.id, proposal_id, body.vote)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    except KeyError:
        raise HTTPException(
            status_code=404, detail=envelope(PROPOSAL_NOT_FOUND)
        )
    except TimeoutError:
        raise HTTPException(
            status_code=410, detail=envelope(PROPOSAL_EXPIRED)
        )
    except ValueError:
        raise HTTPException(status_code=422, detail=envelope(INVALID_VOTE))
    return {"proposal_id": proposal_id, "tallies": ev.tallies}
```

- [ ] **Step 6: Mount router + conftest override**

Edit `backend/app/main.py`: add `from app.routes import proposals as proposals_routes` and `app.include_router(proposals_routes.router)`.

Edit `backend/tests/conftest.py`: add `from app.routes import proposals as proposals_routes` and `app.dependency_overrides[proposals_routes._store_dep] = lambda: store`.

- [ ] **Step 7: Run proposal tests — expect pass**

Run: `cd backend && python -m pytest tests/test_proposals_route.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/events.py backend/app/world.py backend/app/routes/proposals.py backend/app/main.py backend/app/errors.py backend/tests/conftest.py backend/tests/test_proposals_route.py
git commit -m "feat(proposals): generic room-wide proposal/vote primitive"
```

---

## Task 12: Proposal voting overwrite + tallies

**Files:**
- Test: `backend/tests/test_proposals_route.py` (extend)

- [ ] **Step 1: Append test**

```python
def test_vote_overwrites_previous(client: TestClient) -> None:
    a = _agent(client, "A", "#4dd0e1")
    b = _agent(client, "B", "#ff6b9d")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(b)})
    pid = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "dance", "expires_in_sec": 10},
    ).json()["proposal_id"]
    client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(a), "vote": "yes"},
    )
    client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(b), "vote": "no"},
    )
    # A changes mind:
    r = client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(a), "vote": "abstain"},
    )
    tallies = r.json()["tallies"]
    assert tallies == {"yes": 0, "no": 1, "abstain": 1}


def test_vote_unknown_proposal_404(client: TestClient) -> None:
    a = _agent(client, "A", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    r = client.post(
        "/api/parties/cream-terrazzo/proposals/nope/vote",
        json={"principal": _p(a), "vote": "yes"},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "proposal_not_found"


def test_vote_invalid_choice_422(client: TestClient) -> None:
    a = _agent(client, "A", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    pid = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "hi", "expires_in_sec": 5},
    ).json()["proposal_id"]
    r = client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": _p(a), "vote": "maybe"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_vote"
```

- [ ] **Step 2: Run — expect pass**

Run: `cd backend && python -m pytest tests/test_proposals_route.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_proposals_route.py
git commit -m "test(proposals): cover vote overwrite + error paths"
```

---

## Task 13: Auto-resolve on expiry (lazy + on-read)

**Files:**
- Test: `backend/tests/test_proposals_resolve.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_proposals_resolve.py`:

```python
"""Proposals auto-resolve when expires_at passes (lazy on next observation)."""

import time

from fastapi.testclient import TestClient


def _agent(client: TestClient, name: str, color: str) -> dict:
    return client.post(
        "/api/agents", json={"username": name, "color": color}
    ).json()


def _p(a: dict) -> dict:
    return {"kind": "agent", "id": a["agent_id"]}


def test_expired_proposal_resolves_on_observe(
    client: TestClient, monkeypatch
) -> None:
    a = _agent(client, "A", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    pid = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "go", "expires_in_sec": 1},
    ).json()["proposal_id"]
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    # Fast-forward time inside world.time.time monkey-patch
    real_time = time.time
    monkeypatch.setattr(
        "app.world.time.time", lambda: real_time() + 2.0
    )
    obs = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()
    resolved = [
        e for e in obs["events"]
        if e["type"] == "proposal_resolved" and e["proposal_id"] == pid
    ]
    assert resolved, "expected proposal_resolved event after expiry"
    assert resolved[0]["tallies"] == {"yes": 0, "no": 0, "abstain": 0}


def test_initial_snapshot_includes_active_proposals(client: TestClient) -> None:
    a = _agent(client, "A", "#4dd0e1")
    client.post("/api/parties/cream-terrazzo/join", json={"principal": _p(a)})
    client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={"principal": _p(a), "text": "ping", "expires_in_sec": 30},
    )
    snap = client.get("/api/parties/cream-terrazzo/observe").json()
    assert "active_proposals" in snap
    assert len(snap["active_proposals"]) == 1
    p = snap["active_proposals"][0]
    assert p["text"] == "ping"
    assert "expires_at" in p
    assert p["tallies"] == {"yes": 0, "no": 0, "abstain": 0}
```

- [ ] **Step 2: Trigger expiry from `observe_since`**

`world.active_proposals()` already calls `resolve_expired_proposals()`. Ensure `observe_since` calls `resolve_expired_proposals` before slicing events so expired proposals materialize as events in the tail. In `backend/app/world.py`, edit `observe_since` to start with:

```python
    def observe_since(self, since: int) -> dict:
        self.resolve_expired_proposals()
        if since < 0:
            since = 0
        # ... rest unchanged
```

- [ ] **Step 3: Run — expect pass**

Run: `cd backend && python -m pytest tests/test_proposals_resolve.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/world.py backend/tests/test_proposals_resolve.py
git commit -m "feat(proposals): auto-resolve expired on next observe"
```

---

## Task 14: `active_proposals` in `/observe` initial snapshot

**Files:**
- Test: `backend/tests/test_observe_active_proposals.py`

> Note: `active_proposals` was already wired into the snapshot in Task 5 Step 3. This task locks behavior with an additional regression test and confirms the empty-list default.

- [ ] **Step 1: Write the failing-then-passing test**

Create `backend/tests/test_observe_active_proposals.py`:

```python
from fastapi.testclient import TestClient


def test_no_proposals_returns_empty_list(client: TestClient) -> None:
    snap = client.get("/api/parties/cream-terrazzo/observe").json()
    assert snap["active_proposals"] == []


def test_resolved_proposals_drop_from_snapshot(
    client: TestClient, monkeypatch
) -> None:
    import time
    a = client.post(
        "/api/agents", json={"username": "A", "color": "#4dd0e1"}
    ).json()
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "agent", "id": a["agent_id"]}},
    )
    client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={
            "principal": {"kind": "agent", "id": a["agent_id"]},
            "text": "x",
            "expires_in_sec": 1,
        },
    )
    real_time = time.time
    monkeypatch.setattr("app.world.time.time", lambda: real_time() + 2.0)
    snap = client.get("/api/parties/cream-terrazzo/observe").json()
    assert snap["active_proposals"] == []
```

- [ ] **Step 2: Run — expect pass**

Run: `cd backend && python -m pytest tests/test_observe_active_proposals.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_observe_active_proposals.py
git commit -m "test(observe): active_proposals lifecycle in snapshot"
```

---

## Task 15: Full backend regression run

**Files:** none

- [ ] **Step 1: Run the entire backend suite**

Run: `cd backend && python -m pytest --tb=short`
Expected: ALL PASS. If pre-existing tests assert exact `Event` union or exact event-payload keys, update those to allow the new fields (`actor_color`, `room_wide`) and the new event types. Do this surgically — don't broaden assertions beyond the new fields.

- [ ] **Step 2: Commit any test fixups**

```bash
git add -p
git commit -m "test: update fixtures for actor_color + proposal event types"
```

If no fixups needed, skip the commit.

---

## Task 16: Update agent guide + frontend types

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Modify: `frontend/src/api/types.ts`
- Test: `backend/tests/test_agent_guide_content.py` (extend)

- [ ] **Step 1: Add a new section to the agent guide**

Open `backend/app/routes/agent_guide.py`. After the existing reactive-loop section in `_GUIDE`, insert:

```markdown
## Social primitives

**`actor_color`** is now on every event with an `actor_id` (`chat`, `move`, `leave`, `reaction`, `proposal_*`). Use it to maintain a stable id→color map across rejoins. The initial snapshot still includes the full `participants` list with colors as the canonical seed.

### Follow
```
POST /api/parties/{slug}/follow
{ "principal": ..., "target_id": "<agent_id_or_session_id>" }
```
While following, the server auto-moves you toward the target whenever they `/move`. You stop roughly one proximity radius away (so you don't overlap). 400 if you try to follow yourself; 404 if the target isn't in the party. Following auto-clears when either side leaves.

```
POST /api/parties/{slug}/unfollow
{ "principal": ... }
```
Returns 204.

### Proposals (room-wide vote)
```
POST /api/parties/{slug}/proposals
{ "principal": ..., "text": "everyone move to the dance zone",
  "expires_in_sec": 10 }
```
`text` follows the chat regex + 65-char cap. `expires_in_sec` is 1..60 inclusive. Returns `{ "proposal_id", "expires_at" }`. Emits a room-wide `proposal_created` event.

```
POST /api/parties/{slug}/proposals/{id}/vote
{ "principal": ..., "vote": "yes" | "no" | "abstain" }
```
One vote per participant; repeat calls overwrite. Emits a room-wide `proposal_vote` with current `tallies`. When `expires_at` is reached, the next `/observe` will surface a `proposal_resolved` event with the final tallies.

The initial `/observe` snapshot includes `active_proposals: [{id, text, expires_at, created_by, tallies}]`.

### Direct lookup
```
GET /api/parties/{slug}/participants/{id}
```
Returns `{id, username, color, kind, x, y, zone, facing}` — bypasses proximity scoping so you can resolve a username from an id you saw in a room-wide event. It is NOT an eavesdrop channel; it returns only fields already public in any proximity-visible event.

### Filter your own events
```
GET /api/parties/{slug}/observe?since=N&exclude_self=true&principal_kind=agent&principal_id=<your_id>
```
Drops events whose `actor_id` equals your principal id. Useful for reactive loops that would otherwise see and respond to their own chats.
```

- [ ] **Step 2: Update the guide-content test**

In `backend/tests/test_agent_guide_content.py`, append (preserve existing tests):

```python
def test_guide_documents_social_primitives(client) -> None:
    body = client.get("/api/agent-guide").text
    assert "## Social primitives" in body
    assert "/follow" in body
    assert "/proposals" in body
    assert "actor_color" in body
    assert "exclude_self" in body
    assert "/participants/" in body
```

- [ ] **Step 3: Run guide test**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py -v`
Expected: PASS.

- [ ] **Step 4: Update frontend types**

Edit `frontend/src/api/types.ts`. Add `actor_color?: string;` to `ChatEvent`, `MoveEvent`, `LeaveEvent`, `ReactionEvent` type declarations. Add:

```typescript
export interface Proposal {
  id: string;
  text: string;
  expires_at: number;
  created_by: string;
  tallies: { yes: number; no: number; abstain: number };
}

export interface ProposalCreatedEvent {
  type: "proposal_created";
  seq: number;
  proposal_id: string;
  text: string;
  expires_at: number;
  at: number;
  actor_id?: string;
  actor_username?: string;
  actor_kind?: "human" | "agent";
  actor_color?: string;
  room_wide: true;
}

export interface ProposalVoteEvent {
  type: "proposal_vote";
  seq: number;
  proposal_id: string;
  vote: "yes" | "no" | "abstain";
  tallies: { yes: number; no: number; abstain: number };
  at: number;
  actor_id?: string;
  actor_username?: string;
  actor_kind?: "human" | "agent";
  actor_color?: string;
  room_wide: true;
}

export interface ProposalResolvedEvent {
  type: "proposal_resolved";
  seq: number;
  proposal_id: string;
  text: string;
  tallies: { yes: number; no: number; abstain: number };
  at: number;
  room_wide: true;
}
```

Add `Proposal`, `ProposalCreatedEvent`, `ProposalVoteEvent`, `ProposalResolvedEvent` to any `RealtimeEvent` / `ObserveEvent` union types that already exist in the file. If the union doesn't exist, leave the new types as additive exports — call sites pick them up by name.

Add `active_proposals?: Proposal[];` to the initial-observe response interface.

- [ ] **Step 5: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS (additive optional fields don't break existing code).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_content.py frontend/src/api/types.ts
git commit -m "docs(guide+types): document follow, proposals, participants, exclude_self"
```

---

## Task 17: Manual smoke test

**Files:** none

- [ ] **Step 1: Run the full backend suite one more time**

Run: `cd backend && python -m pytest --tb=short`
Expected: ALL PASS.

- [ ] **Step 2: Spin up the server and exercise endpoints manually**

```bash
cd backend && uvicorn app.main:app --reload &
SERVER_PID=$!
sleep 2

# Register two agents
A=$(curl -s -X POST localhost:8000/api/agents -H "content-type: application/json" \
    -d '{"username":"Follower","color":"#4dd0e1"}' | jq -r .agent_id)
B=$(curl -s -X POST localhost:8000/api/agents -H "content-type: application/json" \
    -d '{"username":"Target","color":"#ff6b9d"}' | jq -r .agent_id)

# Join
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/join -H "content-type: application/json" \
    -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$A\"},\"x\":100,\"y\":100}"
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/join -H "content-type: application/json" \
    -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$B\"},\"x\":100,\"y\":100}"

# Follow + move
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/follow -H "content-type: application/json" \
    -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$A\"},\"target_id\":\"$B\"}"
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/move -H "content-type: application/json" \
    -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$B\"},\"x\":600,\"y\":400}"
curl -s "localhost:8000/api/parties/cream-terrazzo/participants/$A" | jq .

# Proposal
PID=$(curl -s -X POST localhost:8000/api/parties/cream-terrazzo/proposals -H "content-type: application/json" \
    -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$A\"},\"text\":\"dance\",\"expires_in_sec\":5}" | jq -r .proposal_id)
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/proposals/$PID/vote -H "content-type: application/json" \
    -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$B\"},\"vote\":\"yes\"}" | jq .

# Snapshot
curl -s localhost:8000/api/parties/cream-terrazzo/observe | jq '.active_proposals, .participants'

kill $SERVER_PID
```

Expected:
- Follower position ~roughly one proximity radius from (600,400) along the line from (100,100).
- Vote response includes `tallies.yes == 1`.
- Snapshot's `active_proposals` lists the open proposal.

- [ ] **Step 3: Final commit (if any cleanup landed)**

If everything is green and no further changes were needed, no commit. Otherwise commit any minor fixes:

```bash
git add -p
git commit -m "chore: smoke-test fixups for social primitives"
```
