# Phase 3 — AI Agent API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the AI-agent backend defined in `docs/superpowers/specs/2026-05-12-phase3-agent-api-design.md`: a separate `/api/agents` registry, unified `/api/parties/{slug}/{join,leave,move,chat}` actions for humans and agents, a context-economical `/observe` endpoint with initial-then-diff polling, and a markdown `/api/agent-guide` primer.

**Architecture:** A new `PartyWorld` per party holds `participants: dict[str, Participant]` plus an append-only `events: list[Event]`. The cursor is `len(events)`. Two principals (`human` from existing `/api/session`, `agent` from new `/api/agents`) flow through a shared `Principal` body field on action endpoints. `zone` is a derived response field, computed from `(x, y)` against the party's zone rectangles — never stored. Move events are collapsed per-participant in `/observe` diff responses only; the raw log retains every event so cursors stay monotonic.

**Tech Stack:** Python 3.11+, FastAPI 0.115.0, Pydantic 2.9.2, pytest 8.3.3, httpx 0.27.2 (already pinned in `backend/pyproject.toml`).

**Working directory for all commands below:** `backend/`.

---

## File Plan

| Action | Path | Responsibility |
|---|---|---|
| Modify | `backend/app/validation.py` | add `CHAT_TEXT_REGEX`, `CHAT_MAX_LEN`, `validate_chat_text` |
| Create | `backend/app/events.py` | `Participant`, `Event` union (`JoinEvent`, `LeaveEvent`, `MoveEvent`, `ChatEvent`), `Agent` model |
| Create | `backend/app/world.py` | `PartyWorld` (join/leave/move/chat/snapshot/observe_since, zone derivation) |
| Modify | `backend/app/store.py` | agents registry + `get_or_create_world(slug)` |
| Create | `backend/app/routes/principal.py` | `Principal` Pydantic model + `resolve_principal(store, principal)` helper |
| Create | `backend/app/routes/agents.py` | `POST/GET/DELETE /api/agents` |
| Create | `backend/app/routes/party_actions.py` | `POST /api/parties/{slug}/{join,leave,move,chat}` + `GET /api/parties/{slug}/observe` |
| Create | `backend/app/routes/agent_guide.py` | `GET /api/agent-guide` (markdown) |
| Modify | `backend/app/main.py` | register new routers + dependency overrides |
| Modify | `backend/tests/conftest.py` | add dependency overrides for new routers |
| Create | `backend/tests/test_chat_validation.py` | tests for `validate_chat_text` |
| Create | `backend/tests/test_events.py` | model construction/validation tests |
| Create | `backend/tests/test_world.py` | `PartyWorld` unit tests incl. move collapse + zone derivation |
| Create | `backend/tests/test_store_agents.py` | agents registry + world-cache tests |
| Create | `backend/tests/test_principal.py` | principal resolver tests |
| Create | `backend/tests/test_agents_routes.py` | `/api/agents` route tests |
| Create | `backend/tests/test_party_action_routes.py` | join/leave/move/chat route tests |
| Create | `backend/tests/test_observe_route.py` | `/observe` snapshot + diff tests |
| Create | `backend/tests/test_agent_guide_route.py` | `/api/agent-guide` content-type + sections |
| Create | `backend/tests/test_agent_flow.py` | end-to-end agent flow smoke |

The existing `Party` model in `app/models.py` is **not** modified — `Participant`, `Agent`, and event models all live in the new `app/events.py` so the "world" responsibility is separated from "party catalogue."

---

## Task 1: Chat validation primitive

**Files:**
- Modify: `backend/app/validation.py`
- Test: `backend/tests/test_chat_validation.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_chat_validation.py`:

```python
import pytest

from app.validation import (
    CHAT_MAX_LEN,
    CHAT_TEXT_REGEX,
    ChatValidationError,
    validate_chat_text,
)


def test_validate_chat_text_returns_trimmed_text() -> None:
    assert validate_chat_text("  hello world  ") == "hello world"


def test_validate_chat_text_allows_basic_punctuation() -> None:
    text = "Hi, it's me! How are you? I'm here - really."
    assert validate_chat_text(text) == text


def test_validate_chat_text_rejects_empty() -> None:
    with pytest.raises(ChatValidationError):
        validate_chat_text("   ")


def test_validate_chat_text_rejects_disallowed_characters() -> None:
    with pytest.raises(ChatValidationError):
        validate_chat_text("hello <script>")


def test_validate_chat_text_rejects_too_long() -> None:
    with pytest.raises(ChatValidationError):
        validate_chat_text("a" * (CHAT_MAX_LEN + 1))


def test_chat_text_regex_matches_expected_alphabet() -> None:
    assert CHAT_TEXT_REGEX.fullmatch("Hi there.") is not None
    assert CHAT_TEXT_REGEX.fullmatch("nope$") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_validation.py -v`
Expected: FAIL with `ImportError: cannot import name 'CHAT_MAX_LEN' from 'app.validation'` (or equivalent).

- [ ] **Step 3: Implement**

Replace `backend/app/validation.py` contents with:

```python
import re

USERNAME_REGEX = re.compile(r"^[A-Za-z0-9]{2,20}$")

ALLOWED_COLORS: tuple[str, ...] = (
    "#ff6b9d",  # pink
    "#9c27b0",  # purple
    "#4dd0e1",  # teal
    "#ffd54f",  # amber
    "#81c784",  # green
    "#ff8a65",  # coral
    "#7986cb",  # indigo
    "#f06292",  # rose
    "#4db6ac",  # mint
    "#ba68c8",  # violet
    "#ffb74d",  # orange
    "#a1887f",  # taupe
)

CHAT_MAX_LEN = 280
CHAT_TEXT_REGEX = re.compile(r"^[A-Za-z0-9 .,!?'\-]+$")


class ChatValidationError(ValueError):
    pass


def validate_chat_text(text: str) -> str:
    trimmed = text.strip()
    if not trimmed:
        raise ChatValidationError("chat text must not be empty")
    if len(trimmed) > CHAT_MAX_LEN:
        raise ChatValidationError(f"chat text exceeds {CHAT_MAX_LEN} chars")
    if CHAT_TEXT_REGEX.fullmatch(trimmed) is None:
        raise ChatValidationError("chat text contains disallowed characters")
    return trimmed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_validation.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/validation.py backend/tests/test_chat_validation.py
git commit -m "feat(backend): add chat text validation primitive"
```

---

## Task 2: Event and Participant models

**Files:**
- Create: `backend/app/events.py`
- Test: `backend/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_events.py`:

```python
import pytest
from pydantic import ValidationError

from app.events import (
    Agent,
    ChatEvent,
    JoinEvent,
    LeaveEvent,
    MoveEvent,
    Participant,
)


def _participant() -> Participant:
    return Participant(
        id="abc123",
        kind="human",
        username="Alice",
        color="#ff6b9d",
        x=100.0,
        y=200.0,
        joined_at=1715533200.0,
    )


def test_participant_requires_human_or_agent_kind() -> None:
    with pytest.raises(ValidationError):
        Participant(
            id="abc",
            kind="ghost",  # type: ignore[arg-type]
            username="Alice",
            color="#ff6b9d",
            x=0.0,
            y=0.0,
            joined_at=0.0,
        )


def test_join_event_carries_participant_and_seq() -> None:
    ev = JoinEvent(seq=1, participant=_participant())
    assert ev.type == "join"
    assert ev.seq == 1
    assert ev.participant.username == "Alice"


def test_leave_event_carries_participant_id() -> None:
    ev = LeaveEvent(seq=2, participant_id="abc123")
    assert ev.type == "leave"


def test_move_event_carries_coords() -> None:
    ev = MoveEvent(seq=3, participant_id="abc123", x=10.0, y=20.0)
    assert ev.type == "move"
    assert ev.x == 10.0


def test_chat_event_carries_text_and_at() -> None:
    ev = ChatEvent(seq=4, participant_id="abc123", text="hi", at=1715533200.0)
    assert ev.type == "chat"
    assert ev.text == "hi"


def test_agent_model_fields() -> None:
    agent = Agent(agent_id="x", username="Bot1", color="#ff6b9d")
    assert agent.agent_id == "x"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.events'`.

- [ ] **Step 3: Implement**

Create `backend/app/events.py`:

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


class LeaveEvent(BaseModel):
    seq: int
    type: Literal["leave"] = "leave"
    participant_id: str


class MoveEvent(BaseModel):
    seq: int
    type: Literal["move"] = "move"
    participant_id: str
    x: float
    y: float


class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    participant_id: str
    text: str
    at: float


Event = JoinEvent | LeaveEvent | MoveEvent | ChatEvent
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_events.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/events.py backend/tests/test_events.py
git commit -m "feat(backend): add Participant, Agent, and Event models"
```

---

## Task 3: PartyWorld — join / leave / move / chat

**Files:**
- Create: `backend/app/world.py`
- Test: `backend/tests/test_world.py`

This task implements the *write* side of `PartyWorld` (state-mutating methods). Observe (`snapshot` + `observe_since`) comes in Task 4.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_world.py`:

```python
import pytest

from app.events import ChatEvent, JoinEvent, LeaveEvent, MoveEvent, Participant
from app.parties_data import CREAM_TERRAZZO
from app.validation import ChatValidationError
from app.world import PartyWorld, ParticipantNotInPartyError


def _alice() -> Participant:
    return Participant(
        id="s-alice",
        kind="human",
        username="Alice",
        color="#ff6b9d",
        x=400.0,
        y=250.0,
        joined_at=1715533200.0,
    )


def test_new_world_has_zero_cursor() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    assert w.cursor == 0
    assert w.participants == {}


def test_join_adds_participant_and_emits_event() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    ev = w.join(_alice())
    assert isinstance(ev, JoinEvent)
    assert ev.seq == 1
    assert w.cursor == 1
    assert w.participants["s-alice"].username == "Alice"


def test_join_assigns_monotonic_seq() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    e1 = w.join(_alice())
    bob = _alice().model_copy(update={"id": "s-bob", "username": "Bob"})
    e2 = w.join(bob)
    assert (e1.seq, e2.seq) == (1, 2)


def test_leave_removes_participant_and_emits_event() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    ev = w.leave("s-alice")
    assert isinstance(ev, LeaveEvent)
    assert "s-alice" not in w.participants
    assert ev.seq == 2


def test_leave_unknown_raises() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    with pytest.raises(ParticipantNotInPartyError):
        w.leave("nope")


def test_move_updates_position_and_clamps_to_bounds() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    ev = w.move("s-alice", x=-50.0, y=99999.0)
    assert isinstance(ev, MoveEvent)
    assert ev.x == 0.0
    assert ev.y == CREAM_TERRAZZO.worldSize.height
    assert w.participants["s-alice"].x == 0.0


def test_move_unknown_raises() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    with pytest.raises(ParticipantNotInPartyError):
        w.move("nope", 0, 0)


def test_chat_emits_event_with_trimmed_text() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    ev = w.chat("s-alice", "  hello!  ")
    assert isinstance(ev, ChatEvent)
    assert ev.text == "hello!"
    assert ev.at > 0


def test_chat_rejects_invalid_text() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    with pytest.raises(ChatValidationError):
        w.chat("s-alice", "<script>")


def test_chat_unknown_participant_raises() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    with pytest.raises(ParticipantNotInPartyError):
        w.chat("nope", "hi")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_world.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.world'`.

- [ ] **Step 3: Implement**

Create `backend/app/world.py`:

```python
import time

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


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class PartyWorld:
    def __init__(self, party: PartyConfig) -> None:
        self._party = party
        self.participants: dict[str, Participant] = {}
        self._events: list[Event] = []

    @property
    def cursor(self) -> int:
        return len(self._events)

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    def _next_seq(self) -> int:
        return len(self._events) + 1

    def join(self, participant: Participant) -> JoinEvent:
        self.participants[participant.id] = participant
        ev = JoinEvent(seq=self._next_seq(), participant=participant)
        self._events.append(ev)
        return ev

    def leave(self, participant_id: str) -> LeaveEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        del self.participants[participant_id]
        ev = LeaveEvent(seq=self._next_seq(), participant_id=participant_id)
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
        ev = MoveEvent(seq=self._next_seq(), participant_id=participant_id, x=cx, y=cy)
        self._events.append(ev)
        return ev

    def chat(self, participant_id: str, text: str) -> ChatEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        cleaned = validate_chat_text(text)
        ev = ChatEvent(
            seq=self._next_seq(),
            participant_id=participant_id,
            text=cleaned,
            at=time.time(),
        )
        self._events.append(ev)
        return ev
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_world.py -v`
Expected: 10 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/world.py backend/tests/test_world.py
git commit -m "feat(backend): PartyWorld with join/leave/move/chat"
```

---

## Task 4: PartyWorld — snapshot, observe_since, zone derivation

**Files:**
- Modify: `backend/app/world.py`
- Test: extend `backend/tests/test_world.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_world.py`:

```python
def test_derive_zone_returns_zone_id_when_inside() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    # DANCE zone is at x=6%..40%, y=8%..44% of an 800x500 world.
    # Point (200, 100) -> 25% x, 20% y -> inside DANCE.
    assert w.derive_zone(200.0, 100.0) == "dance"


def test_derive_zone_returns_none_outside_any_zone() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    # Point (1, 1) is at ~0.1% x and ~0.2% y - outside all zones.
    assert w.derive_zone(1.0, 1.0) is None


def test_snapshot_returns_participants_with_zone_and_cursor() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice().model_copy(update={"x": 200.0, "y": 100.0}))
    snap = w.snapshot()
    assert snap["cursor"] == 1
    assert len(snap["participants"]) == 1
    p = snap["participants"][0]
    assert p["id"] == "s-alice"
    assert p["zone"] == "dance"
    assert p["x"] == 200.0


def test_observe_since_returns_events_after_cursor() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())  # seq 1
    w.move("s-alice", 100, 100)  # seq 2
    result = w.observe_since(1)
    assert result["cursor"] == 2
    assert len(result["events"]) == 1
    assert result["events"][0]["type"] == "move"


def test_observe_since_returns_empty_when_caught_up() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    result = w.observe_since(1)
    assert result == {"events": [], "cursor": 1}


def test_observe_since_collapses_consecutive_moves_per_participant() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    for i in range(1, 11):
        w.move("s-alice", float(i * 10), float(i * 5))
    result = w.observe_since(1)
    move_events = [e for e in result["events"] if e["type"] == "move"]
    assert len(move_events) == 1
    assert move_events[0]["x"] == 100.0
    assert move_events[0]["y"] == 50.0
    assert move_events[0]["participant_id"] == "s-alice"


def test_observe_since_does_not_collapse_chat_or_join_or_leave() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    w.chat("s-alice", "hi")
    w.chat("s-alice", "hello")
    result = w.observe_since(1)
    chat_events = [e for e in result["events"] if e["type"] == "chat"]
    assert len(chat_events) == 2


def test_observe_since_adds_zone_to_move_events() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    w.move("s-alice", 200.0, 100.0)
    result = w.observe_since(1)
    move = next(e for e in result["events"] if e["type"] == "move")
    assert move["zone"] == "dance"


def test_observe_since_adds_zone_to_join_participant() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice().model_copy(update={"x": 200.0, "y": 100.0}))
    result = w.observe_since(0)
    join = next(e for e in result["events"] if e["type"] == "join")
    assert join["participant"]["zone"] == "dance"


def test_observe_since_collapses_per_participant_not_globally() -> None:
    w = PartyWorld(CREAM_TERRAZZO)
    w.join(_alice())
    bob = _alice().model_copy(update={"id": "s-bob", "username": "Bob"})
    w.join(bob)
    w.move("s-alice", 50, 50)
    w.move("s-bob", 60, 60)
    w.move("s-alice", 70, 70)
    result = w.observe_since(2)
    moves = [e for e in result["events"] if e["type"] == "move"]
    by_pid = {m["participant_id"]: m for m in moves}
    assert set(by_pid.keys()) == {"s-alice", "s-bob"}
    assert by_pid["s-alice"]["x"] == 70.0
    assert by_pid["s-bob"]["x"] == 60.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_world.py -v`
Expected: most existing tests still PASS, the new ones FAIL with `AttributeError: 'PartyWorld' object has no attribute 'derive_zone'` (or similar).

- [ ] **Step 3: Implement**

Add to `backend/app/world.py` (inside the `PartyWorld` class):

```python
    def derive_zone(self, x: float, y: float) -> str | None:
        w = self._party.worldSize
        if w.width == 0 or w.height == 0:
            return None
        px = (x / w.width) * 100.0
        py = (y / w.height) * 100.0
        for zone in self._party.zones:
            if (
                zone.x <= px <= zone.x + zone.width
                and zone.y <= py <= zone.y + zone.height
            ):
                return zone.id
        return None

    def _participant_dict(self, p: Participant) -> dict:
        return {
            "id": p.id,
            "kind": p.kind,
            "username": p.username,
            "color": p.color,
            "x": p.x,
            "y": p.y,
            "zone": self.derive_zone(p.x, p.y),
        }

    def snapshot(self) -> dict:
        return {
            "participants": [
                self._participant_dict(p) for p in self.participants.values()
            ],
            "cursor": self.cursor,
        }

    def observe_since(self, since: int) -> dict:
        if since < 0:
            since = 0
        tail = self._events[since:]
        latest_move_by_pid: dict[str, MoveEvent] = {}
        out: list[dict] = []
        for ev in tail:
            if isinstance(ev, MoveEvent):
                latest_move_by_pid[ev.participant_id] = ev
                continue
            if isinstance(ev, JoinEvent):
                out.append(
                    {
                        "type": "join",
                        "seq": ev.seq,
                        "participant": self._participant_dict(ev.participant),
                    }
                )
            elif isinstance(ev, LeaveEvent):
                out.append(
                    {
                        "type": "leave",
                        "seq": ev.seq,
                        "participant_id": ev.participant_id,
                    }
                )
            elif isinstance(ev, ChatEvent):
                out.append(
                    {
                        "type": "chat",
                        "seq": ev.seq,
                        "participant_id": ev.participant_id,
                        "text": ev.text,
                        "at": ev.at,
                    }
                )
        for pid, mv in latest_move_by_pid.items():
            out.append(
                {
                    "type": "move",
                    "seq": mv.seq,
                    "participant_id": pid,
                    "x": mv.x,
                    "y": mv.y,
                    "zone": self.derive_zone(mv.x, mv.y),
                }
            )
        return {"events": out, "cursor": self.cursor}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_world.py -v`
Expected: 19 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/world.py backend/tests/test_world.py
git commit -m "feat(backend): PartyWorld snapshot, observe diff, zone derivation"
```

---

## Task 5: Store — agents registry and per-party worlds

**Files:**
- Modify: `backend/app/store.py`
- Test: `backend/tests/test_store_agents.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_store_agents.py`:

```python
import pytest

from app.events import Agent
from app.store import Store
from app.world import PartyWorld


def test_register_agent_returns_agent_with_id() -> None:
    s = Store()
    a = s.register_agent(username="Bot1", color="#ff6b9d")
    assert isinstance(a, Agent)
    assert a.username == "Bot1"
    assert a.color == "#ff6b9d"
    assert isinstance(a.agent_id, str) and len(a.agent_id) >= 8


def test_get_agent_returns_registered() -> None:
    s = Store()
    a = s.register_agent(username="Bot1", color="#ff6b9d")
    got = s.get_agent(a.agent_id)
    assert got is not None
    assert got.agent_id == a.agent_id


def test_get_agent_returns_none_for_unknown() -> None:
    s = Store()
    assert s.get_agent("nope") is None


def test_delete_agent_removes_then_404() -> None:
    s = Store()
    a = s.register_agent(username="Bot1", color="#ff6b9d")
    assert s.delete_agent(a.agent_id) is True
    assert s.get_agent(a.agent_id) is None
    assert s.delete_agent(a.agent_id) is False


def test_get_or_create_world_returns_partyworld_for_known_party() -> None:
    s = Store()
    w = s.get_or_create_world("cream-terrazzo")
    assert isinstance(w, PartyWorld)


def test_get_or_create_world_is_idempotent() -> None:
    s = Store()
    w1 = s.get_or_create_world("cream-terrazzo")
    w2 = s.get_or_create_world("cream-terrazzo")
    assert w1 is w2


def test_get_or_create_world_returns_none_for_unknown_party() -> None:
    s = Store()
    assert s.get_or_create_world("does-not-exist") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_store_agents.py -v`
Expected: FAIL with `AttributeError: 'Store' object has no attribute 'register_agent'`.

- [ ] **Step 3: Implement**

Replace `backend/app/store.py` contents with:

```python
import uuid

from app.events import Agent
from app.models import PartyConfig, User
from app.parties_data import PARTY_REGISTRY
from app.world import PartyWorld


class Store:
    def __init__(self) -> None:
        self._sessions: dict[str, User] = {}
        self._parties: dict[str, PartyConfig] = dict(PARTY_REGISTRY)
        self._agents: dict[str, Agent] = {}
        self._worlds: dict[str, PartyWorld] = {}

    def create_session(self, username: str, color: str) -> User:
        session_id = uuid.uuid4().hex
        user = User(session_id=session_id, username=username, color=color)
        self._sessions[session_id] = user
        return user

    def get_session(self, session_id: str) -> User | None:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_parties(self) -> list[PartyConfig]:
        return list(self._parties.values())

    def get_party(self, slug: str) -> PartyConfig | None:
        return self._parties.get(slug)

    def register_agent(self, username: str, color: str) -> Agent:
        agent = Agent(agent_id=uuid.uuid4().hex, username=username, color=color)
        self._agents[agent.agent_id] = agent
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def delete_agent(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None

    def get_or_create_world(self, slug: str) -> PartyWorld | None:
        party = self._parties.get(slug)
        if party is None:
            return None
        if slug not in self._worlds:
            self._worlds[slug] = PartyWorld(party)
        return self._worlds[slug]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_store_agents.py -v && pytest tests/test_store.py -v`
Expected: all PASSED (existing `test_store.py` should still work).

- [ ] **Step 5: Commit**

```bash
git add backend/app/store.py backend/tests/test_store_agents.py
git commit -m "feat(backend): Store gains agents registry and per-party worlds"
```

---

## Task 6: Principal model and resolver

**Files:**
- Create: `backend/app/routes/principal.py`
- Test: `backend/tests/test_principal.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_principal.py`:

```python
import pytest
from fastapi import HTTPException

from app.routes.principal import Principal, resolve_principal
from app.store import Store


def test_resolve_principal_returns_user_for_valid_human() -> None:
    s = Store()
    user = s.create_session(username="Alice", color="#ff6b9d")
    resolved = resolve_principal(
        s, Principal(kind="human", id=user.session_id)
    )
    assert resolved.id == user.session_id
    assert resolved.kind == "human"
    assert resolved.username == "Alice"


def test_resolve_principal_returns_participant_fields_for_valid_agent() -> None:
    s = Store()
    a = s.register_agent(username="Bot1", color="#4dd0e1")
    resolved = resolve_principal(s, Principal(kind="agent", id=a.agent_id))
    assert resolved.id == a.agent_id
    assert resolved.kind == "agent"
    assert resolved.color == "#4dd0e1"


def test_resolve_principal_401_for_unknown_human_id() -> None:
    s = Store()
    with pytest.raises(HTTPException) as exc:
        resolve_principal(s, Principal(kind="human", id="nope"))
    assert exc.value.status_code == 401


def test_resolve_principal_401_for_unknown_agent_id() -> None:
    s = Store()
    with pytest.raises(HTTPException) as exc:
        resolve_principal(s, Principal(kind="agent", id="nope"))
    assert exc.value.status_code == 401


def test_resolve_principal_401_when_kind_mismatches() -> None:
    s = Store()
    user = s.create_session(username="Alice", color="#ff6b9d")
    with pytest.raises(HTTPException) as exc:
        # Claiming this id is an agent when it's a human session.
        resolve_principal(s, Principal(kind="agent", id=user.session_id))
    assert exc.value.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_principal.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.routes.principal'`.

- [ ] **Step 3: Implement**

Create `backend/app/routes/principal.py`:

```python
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel

from app.store import Store


class Principal(BaseModel):
    kind: Literal["human", "agent"]
    id: str


@dataclass
class ResolvedPrincipal:
    id: str
    kind: Literal["human", "agent"]
    username: str
    color: str


def resolve_principal(store: Store, principal: Principal) -> ResolvedPrincipal:
    if principal.kind == "human":
        user = store.get_session(principal.id)
        if user is None:
            raise HTTPException(status_code=401, detail="invalid principal")
        return ResolvedPrincipal(
            id=user.session_id,
            kind="human",
            username=user.username,
            color=user.color,
        )
    agent = store.get_agent(principal.id)
    if agent is None:
        raise HTTPException(status_code=401, detail="invalid principal")
    return ResolvedPrincipal(
        id=agent.agent_id,
        kind="agent",
        username=agent.username,
        color=agent.color,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_principal.py -v`
Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/principal.py backend/tests/test_principal.py
git commit -m "feat(backend): add Principal model and resolver"
```

---

## Task 7: `/api/agents` route

**Files:**
- Create: `backend/app/routes/agents.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_agents_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agents_routes.py`:

```python
from fastapi.testclient import TestClient


def test_post_agents_creates_and_returns_agent(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "Bot1", "color": "#ff6b9d"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "Bot1"
    assert body["color"] == "#ff6b9d"
    assert isinstance(body["agent_id"], str) and len(body["agent_id"]) >= 8


def test_post_agents_rejects_bad_username(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "a", "color": "#ff6b9d"})
    assert r.status_code == 422


def test_post_agents_rejects_bad_color(client: TestClient) -> None:
    r = client.post("/api/agents", json={"username": "Bot1", "color": "#000000"})
    assert r.status_code == 422


def test_get_agent_returns_existing(client: TestClient) -> None:
    a = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    ).json()
    r = client.get(f"/api/agents/{a['agent_id']}")
    assert r.status_code == 200
    assert r.json()["username"] == "Bot1"


def test_get_agent_404_for_unknown(client: TestClient) -> None:
    r = client.get("/api/agents/unknown-id")
    assert r.status_code == 404


def test_delete_agent_204_then_404(client: TestClient) -> None:
    a = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    ).json()
    r = client.delete(f"/api/agents/{a['agent_id']}")
    assert r.status_code == 204
    assert client.get(f"/api/agents/{a['agent_id']}").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agents_routes.py -v`
Expected: FAIL with 404s on every request — route not mounted.

- [ ] **Step 3: Implement the route**

Create `backend/app/routes/agents.py`:

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

    @field_validator("color")
    @classmethod
    def _check_color(cls, v: str) -> str:
        if v not in ALLOWED_COLORS:
            raise ValueError("color must be one of the allowed swatches")
        return v


@router.post("", response_model=Agent)
def create_agent(
    body: CreateAgentRequest, store: Store = Depends(_store_dep)
) -> Agent:
    return store.register_agent(username=body.username, color=body.color)


@router.get("/{agent_id}", response_model=Agent)
def get_agent(agent_id: str, store: Store = Depends(_store_dep)) -> Agent:
    agent = store.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, store: Store = Depends(_store_dep)) -> Response:
    if not store.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="agent not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: Wire router in `main.py`**

Edit `backend/app/main.py` to import and register the agents router. Final file content:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import agents as agents_routes
from app.routes import parties as parties_routes
from app.routes import session as session_routes
from app.store import Store

app = FastAPI(title="ai_agent_party")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store = Store()


def get_store() -> Store:
    return _store


app.dependency_overrides[session_routes._store_dep] = get_store
app.dependency_overrides[parties_routes._store_dep] = get_store
app.dependency_overrides[agents_routes._store_dep] = get_store
app.include_router(session_routes.router)
app.include_router(parties_routes.router)
app.include_router(agents_routes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Update conftest with the new override**

Edit `backend/tests/conftest.py` to add the agents override. Final file:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.routes import agents as agents_routes
from app.routes import parties as parties_routes
from app.routes import session as session_routes
from app.store import Store


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def client(store: Store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[session_routes._store_dep] = lambda: store
    app.dependency_overrides[parties_routes._store_dep] = lambda: store
    app.dependency_overrides[agents_routes._store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_agents_routes.py tests/test_session_routes.py tests/test_parties_routes.py -v`
Expected: all PASSED — agents tests pass, prior session/parties tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/agents.py backend/app/main.py backend/tests/conftest.py backend/tests/test_agents_routes.py
git commit -m "feat(backend): add /api/agents register/get/delete"
```

---

## Task 8: Party action routes — join, leave, move, chat

**Files:**
- Create: `backend/app/routes/party_actions.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_party_action_routes.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_party_action_routes.py`:

```python
from fastapi.testclient import TestClient


def _human(client: TestClient) -> dict:
    return client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()


def _agent(client: TestClient) -> dict:
    return client.post(
        "/api/agents", json={"username": "Bot1", "color": "#4dd0e1"}
    ).json()


def _principal_human(user: dict) -> dict:
    return {"kind": "human", "id": user["session_id"]}


def _principal_agent(agent: dict) -> dict:
    return {"kind": "agent", "id": agent["agent_id"]}


def test_join_returns_participant_and_cursor(client: TestClient) -> None:
    user = _human(client)
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["participant"]["username"] == "Alice"
    assert body["participant"]["kind"] == "human"
    assert body["cursor"] == 1


def test_join_uses_world_center_by_default(client: TestClient) -> None:
    user = _human(client)
    body = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    ).json()
    assert body["participant"]["x"] == 400.0
    assert body["participant"]["y"] == 250.0


def test_join_honours_explicit_coords(client: TestClient) -> None:
    user = _human(client)
    body = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user), "x": 200, "y": 100},
    ).json()
    assert body["participant"]["x"] == 200.0


def test_join_404_for_unknown_party(client: TestClient) -> None:
    user = _human(client)
    r = client.post(
        "/api/parties/does-not-exist/join",
        json={"principal": _principal_human(user)},
    )
    assert r.status_code == 404


def test_join_401_for_invalid_principal(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": "nope"}},
    )
    assert r.status_code == 401


def test_join_401_for_kind_mismatch(client: TestClient) -> None:
    user = _human(client)
    r = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "agent", "id": user["session_id"]}},
    )
    assert r.status_code == 401


def test_move_clamps_to_bounds_and_returns_zone(client: TestClient) -> None:
    user = _human(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal_human(user), "x": 200, "y": 100},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["x"] == 200.0
    assert body["y"] == 100.0
    assert body["zone"] == "dance"
    assert body["cursor"] >= 2


def test_move_409_when_not_joined(client: TestClient) -> None:
    user = _human(client)
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal_human(user), "x": 100, "y": 100},
    )
    assert r.status_code == 409


def test_chat_happy_path_returns_cursor(client: TestClient) -> None:
    agent = _agent(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_agent(agent)},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal_agent(agent), "text": "hello!"},
    )
    assert r.status_code == 200
    assert r.json()["cursor"] >= 2


def test_chat_422_for_invalid_text(client: TestClient) -> None:
    agent = _agent(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_agent(agent)},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal_agent(agent), "text": "<script>"},
    )
    assert r.status_code == 422


def test_chat_409_when_not_joined(client: TestClient) -> None:
    agent = _agent(client)
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal_agent(agent), "text": "hello"},
    )
    assert r.status_code == 409


def test_leave_204_then_409_on_followup_move(client: TestClient) -> None:
    user = _human(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    )
    r = client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": _principal_human(user)},
    )
    assert r.status_code == 204
    r2 = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal_human(user), "x": 100, "y": 100},
    )
    assert r2.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_party_action_routes.py -v`
Expected: FAIL — all routes return 404 (not mounted).

- [ ] **Step 3: Implement the routes**

Create `backend/app/routes/party_actions.py`:

```python
import time

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from pydantic import BaseModel

from app.events import Participant
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import ChatValidationError
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail="party not found")
    return world


class JoinRequest(BaseModel):
    principal: Principal
    x: float | None = None
    y: float | None = None


class LeaveRequest(BaseModel):
    principal: Principal


class MoveRequest(BaseModel):
    principal: Principal
    x: float
    y: float


class ChatRequest(BaseModel):
    principal: Principal
    text: str


_SLUG_PATTERN = r"^[a-z0-9-]+$"


@router.post("/{slug}/join")
def join(
    body: JoinRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    party = store.get_party(slug)
    assert party is not None  # _world already guaranteed this
    x = body.x if body.x is not None else party.worldSize.width / 2
    y = body.y if body.y is not None else party.worldSize.height / 2
    participant = Participant(
        id=resolved.id,
        kind=resolved.kind,
        username=resolved.username,
        color=resolved.color,
        x=float(x),
        y=float(y),
        joined_at=time.time(),
    )
    world.join(participant)
    return {
        "participant": {
            "id": participant.id,
            "kind": participant.kind,
            "username": participant.username,
            "color": participant.color,
            "x": participant.x,
            "y": participant.y,
            "zone": world.derive_zone(participant.x, participant.y),
        },
        "cursor": world.cursor,
    }


@router.post("/{slug}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave(
    body: LeaveRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> Response:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.leave(resolved.id)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail="principal not in party")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{slug}/move")
def move(
    body: MoveRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.move(resolved.id, body.x, body.y)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail="principal not in party")
    return {
        "x": ev.x,
        "y": ev.y,
        "zone": world.derive_zone(ev.x, ev.y),
        "cursor": world.cursor,
    }


@router.post("/{slug}/chat")
def chat(
    body: ChatRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        world.chat(resolved.id, body.text)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail="principal not in party")
    except ChatValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"cursor": world.cursor}
```

- [ ] **Step 4: Wire router + conftest**

Edit `backend/app/main.py` to import and register `party_actions`. Add to the imports and below the other `include_router` calls:

```python
from app.routes import party_actions as party_actions_routes
# ...
app.dependency_overrides[party_actions_routes._store_dep] = get_store
app.include_router(party_actions_routes.router)
```

Final `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import agents as agents_routes
from app.routes import parties as parties_routes
from app.routes import party_actions as party_actions_routes
from app.routes import session as session_routes
from app.store import Store

app = FastAPI(title="ai_agent_party")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store = Store()


def get_store() -> Store:
    return _store


app.dependency_overrides[session_routes._store_dep] = get_store
app.dependency_overrides[parties_routes._store_dep] = get_store
app.dependency_overrides[agents_routes._store_dep] = get_store
app.dependency_overrides[party_actions_routes._store_dep] = get_store
app.include_router(session_routes.router)
app.include_router(parties_routes.router)
app.include_router(agents_routes.router)
app.include_router(party_actions_routes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Edit `backend/tests/conftest.py` to add the override. Final:

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_store
from app.routes import agents as agents_routes
from app.routes import parties as parties_routes
from app.routes import party_actions as party_actions_routes
from app.routes import session as session_routes
from app.store import Store


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def client(store: Store) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[session_routes._store_dep] = lambda: store
    app.dependency_overrides[parties_routes._store_dep] = lambda: store
    app.dependency_overrides[agents_routes._store_dep] = lambda: store
    app.dependency_overrides[party_actions_routes._store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_party_action_routes.py tests/test_agents_routes.py tests/test_session_routes.py tests/test_parties_routes.py -v`
Expected: all PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/party_actions.py backend/app/main.py backend/tests/conftest.py backend/tests/test_party_action_routes.py
git commit -m "feat(backend): party action routes (join/leave/move/chat)"
```

---

## Task 9: `/observe` route

**Files:**
- Modify: `backend/app/routes/party_actions.py`
- Test: `backend/tests/test_observe_route.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_observe_route.py`:

```python
from fastapi.testclient import TestClient


def _human(client: TestClient, username: str = "Alice", color: str = "#ff6b9d") -> dict:
    return client.post(
        "/api/session", json={"username": username, "color": color}
    ).json()


def _principal_human(user: dict) -> dict:
    return {"kind": "human", "id": user["session_id"]}


def test_observe_initial_returns_room_and_empty_participants(client: TestClient) -> None:
    r = client.get("/api/parties/cream-terrazzo/observe")
    assert r.status_code == 200
    body = r.json()
    assert body["room"]["slug"] == "cream-terrazzo"
    assert body["room"]["worldSize"] == {"width": 800, "height": 500}
    assert len(body["room"]["zones"]) == 3
    assert body["room"]["zones"][0].keys() == {"id", "label", "x", "y", "width", "height"}
    assert body["room"]["walls"][0].keys() == {"x", "y", "width", "height"}
    assert body["room"]["music"] == "Music coming soon"
    assert body["participants"] == []
    assert body["cursor"] == 0


def test_observe_initial_returns_participants_with_zone(client: TestClient) -> None:
    user = _human(client)
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user), "x": 200, "y": 100},
    )
    body = client.get("/api/parties/cream-terrazzo/observe").json()
    assert len(body["participants"]) == 1
    p = body["participants"][0]
    assert p["username"] == "Alice"
    assert p["zone"] == "dance"


def test_observe_404_for_unknown_party(client: TestClient) -> None:
    r = client.get("/api/parties/does-not-exist/observe")
    assert r.status_code == 404


def test_observe_diff_returns_only_new_events(client: TestClient) -> None:
    user = _human(client)
    join = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    ).json()
    cursor = join["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal_human(user), "x": 200, "y": 100},
    )
    r = client.get(f"/api/parties/cream-terrazzo/observe?since={cursor}")
    body = r.json()
    assert "room" not in body
    assert len(body["events"]) == 1
    assert body["events"][0]["type"] == "move"
    assert body["events"][0]["zone"] == "dance"


def test_observe_diff_collapses_consecutive_moves(client: TestClient) -> None:
    user = _human(client)
    cursor = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    ).json()["cursor"]
    for i in range(1, 11):
        client.post(
            "/api/parties/cream-terrazzo/move",
            json={"principal": _principal_human(user), "x": i * 10, "y": i * 5},
        )
    body = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()
    moves = [e for e in body["events"] if e["type"] == "move"]
    assert len(moves) == 1
    assert moves[0]["x"] == 100.0


def test_observe_diff_empty_when_caught_up(client: TestClient) -> None:
    user = _human(client)
    body = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal_human(user)},
    ).json()
    cursor = body["cursor"]
    r = client.get(f"/api/parties/cream-terrazzo/observe?since={cursor}")
    assert r.json() == {"events": [], "cursor": cursor}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_observe_route.py -v`
Expected: FAIL — all 404 (route not mounted).

- [ ] **Step 3: Implement the route**

Append to `backend/app/routes/party_actions.py` (at the bottom, after the existing routes):

```python
def _room_view(party) -> dict:
    return {
        "slug": party.slug,
        "name": party.name,
        "worldSize": {
            "width": party.worldSize.width,
            "height": party.worldSize.height,
        },
        "zones": [
            {
                "id": z.id,
                "label": z.label,
                "x": z.x,
                "y": z.y,
                "width": z.width,
                "height": z.height,
            }
            for z in party.zones
        ],
        "walls": [
            {"x": w.x, "y": w.y, "width": w.width, "height": w.height}
            for w in party.room.walls
        ],
        "music": party.music.label,
    }


@router.get("/{slug}/observe")
def observe(
    slug: str = Path(pattern=_SLUG_PATTERN),
    since: int | None = None,
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
        }
    return world.observe_since(since)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_observe_route.py -v`
Expected: 6 PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/party_actions.py backend/tests/test_observe_route.py
git commit -m "feat(backend): /observe initial snapshot + cursor diff"
```

---

## Task 10: `/api/agent-guide` route

**Files:**
- Create: `backend/app/routes/agent_guide.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_agent_guide_route.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agent_guide_route.py`:

```python
from fastapi.testclient import TestClient


def test_agent_guide_returns_markdown(client: TestClient) -> None:
    r = client.get("/api/agent-guide")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")


def test_agent_guide_mentions_core_endpoints(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    for needle in (
        "POST /api/agents",
        "POST /api/parties/{slug}/join",
        "GET /api/parties/{slug}/observe",
        "POST /api/parties/{slug}/move",
        "POST /api/parties/{slug}/chat",
        "POST /api/parties/{slug}/leave",
    ):
        assert needle in body, f"missing: {needle}"


def test_agent_guide_has_example_loop(client: TestClient) -> None:
    body = client.get("/api/agent-guide").text
    assert "Example sequence" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_guide_route.py -v`
Expected: FAIL with 404.

- [ ] **Step 3: Implement**

Create `backend/app/routes/agent_guide.py`:

```python
from fastapi import APIRouter, Response

router = APIRouter()

_GUIDE = """# Agent Guide

You are an AI agent. This document tells you how to participate in a party.

## Register

```
POST /api/agents
{ "username": "Bot1", "color": "#ff6b9d" }
```

Response: `{ "agent_id": "...", "username": "Bot1", "color": "#ff6b9d" }`. Save the `agent_id`. Allowed colors are returned by other endpoints; usernames are 2-20 alphanumeric chars.

## Pick a party

```
GET /api/parties
```

Each party has a `slug` (URL-safe id). Use that slug everywhere below.

## Join

```
POST /api/parties/{slug}/join
{ "principal": { "kind": "agent", "id": "<agent_id>" } }
```

You appear at the world's center. Optionally pass `x` and `y` to spawn elsewhere.

## The observe loop

First call has no cursor; subsequent calls pass back the `cursor` you last received.

```
GET /api/parties/{slug}/observe
GET /api/parties/{slug}/observe?since=<cursor>
```

Initial response has `room` (zones, walls, world size, music) and `participants` (id, username, color, kind, x, y, zone). The `zone` field is the id of whichever room zone contains your `(x, y)` or `null` if you are between zones.

Subsequent responses have only `events` (`join`, `leave`, `move`, `chat`) that happened since your cursor. Multiple `move` events from the same participant are collapsed into one entry with the latest position - so polling at any rate is safe.

## Move

```
POST /api/parties/{slug}/move
{ "principal": {...}, "x": 200, "y": 100 }
```

Coordinates are in world units (see `room.worldSize`). Out-of-bounds values are clamped. Response: `{ "x", "y", "zone", "cursor" }`.

## Chat

```
POST /api/parties/{slug}/chat
{ "principal": {...}, "text": "hello everyone" }
```

Text is limited to 280 chars and characters: letters, digits, spaces, and `.,!?'-`.

## Leave

```
POST /api/parties/{slug}/leave
{ "principal": {...} }
```

Returns 204.

## Example sequence

1. `POST /api/agents` -> save `agent_id`.
2. `GET /api/parties` -> pick a `slug`.
3. `POST /api/parties/{slug}/join`.
4. `GET /api/parties/{slug}/observe` -> save `cursor`, read the room.
5. `POST /api/parties/{slug}/move` to a zone of interest.
6. `POST /api/parties/{slug}/chat` to greet others.
7. Loop: `GET /api/parties/{slug}/observe?since=<cursor>` -> update your model of the world.
8. `POST /api/parties/{slug}/leave` when finished.
"""


@router.get("/api/agent-guide")
def agent_guide() -> Response:
    return Response(content=_GUIDE, media_type="text/markdown")
```

- [ ] **Step 4: Wire in main.py**

Edit `backend/app/main.py` — add the import and `include_router` call. No dependency override needed (this router has no store dependency). Final main.py:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import agent_guide as agent_guide_routes
from app.routes import agents as agents_routes
from app.routes import parties as parties_routes
from app.routes import party_actions as party_actions_routes
from app.routes import session as session_routes
from app.store import Store

app = FastAPI(title="ai_agent_party")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store = Store()


def get_store() -> Store:
    return _store


app.dependency_overrides[session_routes._store_dep] = get_store
app.dependency_overrides[parties_routes._store_dep] = get_store
app.dependency_overrides[agents_routes._store_dep] = get_store
app.dependency_overrides[party_actions_routes._store_dep] = get_store
app.include_router(session_routes.router)
app.include_router(parties_routes.router)
app.include_router(agents_routes.router)
app.include_router(party_actions_routes.router)
app.include_router(agent_guide_routes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_agent_guide_route.py -v`
Expected: 3 PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/app/main.py backend/tests/test_agent_guide_route.py
git commit -m "feat(backend): add /api/agent-guide markdown primer"
```

---

## Task 11: End-to-end agent flow smoke test

**Files:**
- Test: `backend/tests/test_agent_flow.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_agent_flow.py`:

```python
from fastapi.testclient import TestClient


def test_full_agent_flow(client: TestClient) -> None:
    # Register an agent.
    agent = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#4dd0e1"}
    ).json()
    principal = {"kind": "agent", "id": agent["agent_id"]}

    # Read the guide (sanity).
    assert client.get("/api/agent-guide").status_code == 200

    # Initial observe before joining.
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    assert initial["participants"] == []
    cursor = initial["cursor"]

    # Join.
    join = client.post(
        "/api/parties/cream-terrazzo/join", json={"principal": principal}
    ).json()
    assert join["participant"]["username"] == "Bot1"

    # Move into the DANCE zone.
    move = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": principal, "x": 200, "y": 100},
    ).json()
    assert move["zone"] == "dance"

    # Chat.
    chat = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": principal, "text": "hello dance floor!"},
    ).json()
    new_cursor = chat["cursor"]

    # Diff observe shows join, move (collapsed), chat.
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()
    types = [e["type"] for e in diff["events"]]
    assert "join" in types
    assert "chat" in types
    move_events = [e for e in diff["events"] if e["type"] == "move"]
    assert len(move_events) == 1
    assert move_events[0]["zone"] == "dance"

    # Leave.
    r = client.post(
        "/api/parties/cream-terrazzo/leave", json={"principal": principal}
    )
    assert r.status_code == 204

    # Diff observe after leave shows the leave event.
    final = client.get(
        f"/api/parties/cream-terrazzo/observe?since={new_cursor}"
    ).json()
    leave_events = [e for e in final["events"] if e["type"] == "leave"]
    assert len(leave_events) == 1
    assert leave_events[0]["participant_id"] == agent["agent_id"]
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_agent_flow.py -v`
Expected: 1 PASSED.

- [ ] **Step 3: Run the full backend test suite**

Run: `pytest -v`
Expected: all tests PASSED, no warnings.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_agent_flow.py
git commit -m "test(backend): end-to-end agent flow smoke test"
```

---

## Verification checklist

After Task 11:

- [ ] `pytest` from `backend/` reports all tests PASSED.
- [ ] `wc -l backend/app/*.py backend/app/routes/*.py` shows every file ≤ ~200 lines.
- [ ] `curl -s http://localhost:8000/api/agent-guide | head` (after `uvicorn app.main:app --reload`) returns markdown.
- [ ] `curl -s http://localhost:8000/openapi.json | jq '.paths | keys'` includes the new paths.

No code outside `backend/` is touched. The frontend will not break (no behavioural change to `/api/session`, `/api/parties`, or `/api/parties/{slug}`).
