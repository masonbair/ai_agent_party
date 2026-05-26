# Spec #07: Music Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a room-wide music control endpoint (`POST /api/parties/{slug}/music`) that mirrors the existing `/lighting` template — supporting play/pause/skip/set_volume actions against a fixed allow-list of track IDs, emitting a `music_changed` event, persisting current music state in `PartyWorld`, exposing that state in `/observe`, and rate-limiting via spec #03's shared token-bucket module.

**Architecture:**
- Backend mirrors `app/routes/lighting.py` and `PartyWorld.set_lighting` exactly. Music state lives on `PartyWorld` as a `MusicState` instance (track_id, playing, volume, since). The endpoint dispatches on `action`, validates the track against `MUSIC_TRACK_ALLOWLIST`, and emits one `music_changed` event with `room_wide=True`.
- Cooldown uses spec #03's `app.rate_limit.acquire(scope="music", principal_id=..., burst=2, refill_per_sec=0.2)` helper (reused, not forked).
- `/observe` swaps the hard-coded `"Music coming soon"` string for the live `MusicState` dict.
- Frontend only adds the type definitions and lets the existing `MusicPill` display the live `track_id` if the new state is provided — no playback engine, no UI controls in this plan.

**Tech Stack:** FastAPI, Pydantic v2, pytest, Vitest, React.

**Assumes merged:** specs #01 (unified event shape + error envelope), #02 (proximity), #03 (shared `app.rate_limit` module with `acquire(scope, principal_id, burst, refill_per_sec) -> bool` and `RateLimited` exception).

---

## Spec → Task map

| Spec requirement | Task(s) |
|---|---|
| 1. `POST /api/parties/{slug}/music` endpoint | 5, 6 |
| 2. `MUSIC_TRACK_ALLOWLIST` in `validation.py`, 422 with `allowed_tracks` | 1, 5 |
| 3. Volume 0-100 int, 422 on invalid | 1, 5 |
| 4. `music_changed` event with unified actor + room_wide=True | 2, 4 |
| 5. `/observe` snapshot includes `music: {track_id, playing, volume, since}` | 3, 7 |
| 6. Per-party music state on `PartyWorld` | 3, 4 |
| 7. Cooldown: burst 2, refill 1 per 5 sec, scope `"music"` | 6 |
| 8. Agent guide update | 8 |
| 9. Frontend types + `MusicPill` shows track_id | 9, 10 |

---

## File Structure

**Create:**
- `backend/tests/test_music_validation.py` — allow-list + volume validation
- `backend/tests/test_music_world.py` — `PartyWorld.set_music` behavior + event emission
- `backend/tests/test_music_route.py` — endpoint integration tests
- `backend/app/routes/music.py` — route handler (mirror of `lighting.py`)

**Modify:**
- `backend/app/validation.py` — add `MUSIC_TRACK_ALLOWLIST`, `MUSIC_VOLUME_MIN/MAX`, validators
- `backend/app/events.py` — add `MusicChangedEvent`, add to `Event` union
- `backend/app/world.py` — add `MusicState`, init music attr, `set_music()` method, expose in `snapshot()`
- `backend/app/routes/party_actions.py` — replace `"music": party.music.label` with live music dict in `_room_view`/observe response
- `backend/app/main.py` — mount music router + override `_store_dep`
- `backend/app/errors.py` — add `INVALID_TRACK`, `INVALID_VOLUME`, `INVALID_ACTION`, `RATE_LIMITED_MUSIC` codes
- `backend/app/routes/agent_guide.py` — document `/music`, allow-list, event, cooldown
- `frontend/src/api/types.ts` — add `MusicState`, `MusicChangedEvent`, `MusicTrackId`
- `frontend/src/components/MusicPill.tsx` — accept optional `trackId` prop, show it when present
- `frontend/src/components/PartySpace.tsx` — wire `music?.track_id` from observe into `MusicPill`
- `backend/tests/test_observe_route.py` — update `Music coming soon` expectation

---

## Task 1: Validation — allow-list, volume, action

**Files:**
- Create: `backend/tests/test_music_validation.py`
- Modify: `backend/app/validation.py`
- Modify: `backend/app/errors.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_music_validation.py
import pytest
from app.validation import (
    MUSIC_TRACK_ALLOWLIST,
    MUSIC_VOLUME_MIN,
    MUSIC_VOLUME_MAX,
    MusicValidationError,
    validate_music_track,
    validate_music_volume,
    validate_music_action,
)


def test_allowlist_contains_the_five_placeholder_ids():
    assert set(MUSIC_TRACK_ALLOWLIST) == {
        "lofi-loop",
        "jazz-club",
        "synthwave",
        "ambient-1",
        "party-mix",
    }


def test_validate_music_track_accepts_allowed():
    assert validate_music_track("lofi-loop") == "lofi-loop"


def test_validate_music_track_rejects_unknown():
    with pytest.raises(MusicValidationError) as exc:
        validate_music_track("rickroll")
    assert "unknown track" in str(exc.value)


def test_validate_music_track_rejects_empty():
    with pytest.raises(MusicValidationError):
        validate_music_track("")


def test_volume_bounds_constants():
    assert MUSIC_VOLUME_MIN == 0
    assert MUSIC_VOLUME_MAX == 100


@pytest.mark.parametrize("v", [0, 1, 50, 99, 100])
def test_validate_music_volume_accepts_range(v):
    assert validate_music_volume(v) == v


@pytest.mark.parametrize("v", [-1, 101, 200])
def test_validate_music_volume_rejects_out_of_range(v):
    with pytest.raises(MusicValidationError):
        validate_music_volume(v)


def test_validate_music_volume_rejects_non_int():
    with pytest.raises(MusicValidationError):
        validate_music_volume(50.5)  # type: ignore[arg-type]


def test_validate_music_volume_rejects_bool():
    # bool is a subclass of int in Python; we must reject it explicitly.
    with pytest.raises(MusicValidationError):
        validate_music_volume(True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "a", ["play", "pause", "skip", "set_volume"]
)
def test_validate_music_action_accepts_known(a):
    assert validate_music_action(a) == a


def test_validate_music_action_rejects_unknown():
    with pytest.raises(MusicValidationError):
        validate_music_action("stop")
```

- [ ] **Step 2: Run tests and watch them fail**

Run: `cd backend && pytest tests/test_music_validation.py -x --tb=short`
Expected: ImportError (symbols not defined).

- [ ] **Step 3: Implement validators**

Append to `backend/app/validation.py`:

```python
# --- music module ---------------------------------------------------------

MUSIC_TRACK_ALLOWLIST: tuple[str, ...] = (
    "lofi-loop",
    "jazz-club",
    "synthwave",
    "ambient-1",
    "party-mix",
)

MUSIC_VOLUME_MIN = 0
MUSIC_VOLUME_MAX = 100

MUSIC_ACTIONS: tuple[str, ...] = ("play", "pause", "skip", "set_volume")


class MusicValidationError(ValueError):
    pass


def validate_music_track(track_id: str) -> str:
    if not isinstance(track_id, str) or not track_id:
        raise MusicValidationError("track_id is required")
    if track_id not in MUSIC_TRACK_ALLOWLIST:
        raise MusicValidationError(
            f"unknown track {track_id!r}; allowed={list(MUSIC_TRACK_ALLOWLIST)}"
        )
    return track_id


def validate_music_volume(volume: int) -> int:
    # bool is a subclass of int — reject explicitly so True/False can't slip in.
    if isinstance(volume, bool) or not isinstance(volume, int):
        raise MusicValidationError("volume must be an integer")
    if volume < MUSIC_VOLUME_MIN or volume > MUSIC_VOLUME_MAX:
        raise MusicValidationError(
            f"volume must be {MUSIC_VOLUME_MIN}..{MUSIC_VOLUME_MAX}"
        )
    return volume


def validate_music_action(action: str) -> str:
    if action not in MUSIC_ACTIONS:
        raise MusicValidationError(
            f"unknown action {action!r}; allowed={list(MUSIC_ACTIONS)}"
        )
    return action
```

Append error codes to `backend/app/errors.py`:

```python
INVALID_TRACK = "invalid_track"
INVALID_VOLUME = "invalid_volume"
INVALID_ACTION = "invalid_action"
RATE_LIMITED_MUSIC = "rate_limited_music"
```

- [ ] **Step 4: Run tests and verify pass**

Run: `cd backend && pytest tests/test_music_validation.py -x --tb=short`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/validation.py backend/app/errors.py backend/tests/test_music_validation.py
git commit -m "feat(music): add track allow-list, volume, action validators"
```

---

## Task 2: `MusicChangedEvent` model

**Files:**
- Modify: `backend/app/events.py`
- Create (test additions): `backend/tests/test_music_world.py`

- [ ] **Step 1: Write failing test for the event model**

Create `backend/tests/test_music_world.py`:

```python
from app.events import MusicChangedEvent, Event


def test_music_changed_event_has_unified_actor_fields():
    ev = MusicChangedEvent(
        seq=1,
        track_id="lofi-loop",
        playing=True,
        volume=42,
        at=12345.0,
        actor_id="agent_x",
        actor_username="DJ",
        actor_kind="agent",
        room_wide=True,
    )
    assert ev.type == "music_changed"
    assert ev.track_id == "lofi-loop"
    assert ev.playing is True
    assert ev.volume == 42
    assert ev.actor_id == "agent_x"
    assert ev.room_wide is True


def test_music_changed_event_is_in_event_union():
    # Pydantic discriminator wiring sanity-check.
    assert MusicChangedEvent in Event.__args__  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run and watch fail**

Run: `cd backend && pytest tests/test_music_world.py::test_music_changed_event_has_unified_actor_fields -x --tb=short`
Expected: ImportError on `MusicChangedEvent`.

- [ ] **Step 3: Add the event model**

Append to `backend/app/events.py` (before the `Event = (...)` union definition):

```python
class MusicChangedEvent(BaseModel):
    seq: int
    type: Literal["music_changed"] = "music_changed"
    track_id: str
    playing: bool
    volume: int
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    room_wide: bool = True
```

Then extend the `Event` union to include `MusicChangedEvent`:

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
    | MusicChangedEvent
)
```

- [ ] **Step 4: Verify pass**

Run: `cd backend && pytest tests/test_music_world.py -x --tb=short`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/events.py backend/tests/test_music_world.py
git commit -m "feat(music): add MusicChangedEvent to event union"
```

---

## Task 3: `MusicState` + initial value on `PartyWorld`

**Files:**
- Modify: `backend/app/world.py`
- Modify: `backend/tests/test_music_world.py`

- [ ] **Step 1: Add failing tests for initial state and snapshot**

Append to `backend/tests/test_music_world.py`:

```python
from app.models import (
    PartyConfig,
    Room,
    Theme,
    Music,
    WorldSize,
)
from app.world import PartyWorld, MusicState


def _make_world() -> PartyWorld:
    party = PartyConfig(
        slug="t",
        name="T",
        description="",
        theme=Theme(floor="#fff", accent="#000"),
        zones=[],
        music=Music(url=None, label="Music coming soon"),
        worldSize=WorldSize(width=400, height=300),
        room=Room(clipPath=None, border="1px solid #000", walls=[]),
        modules=[],
    )
    return PartyWorld(party)


def test_initial_music_state_defaults():
    w = _make_world()
    assert isinstance(w.music, MusicState)
    assert w.music.track_id is None
    assert w.music.playing is False
    assert w.music.volume == 50
    assert w.music.since is None


def test_snapshot_includes_music_state():
    w = _make_world()
    snap = w.snapshot()
    assert "music" in snap
    assert snap["music"] == {
        "track_id": None,
        "playing": False,
        "volume": 50,
        "since": None,
    }
```

- [ ] **Step 2: Run and watch fail**

Run: `cd backend && pytest tests/test_music_world.py -x --tb=short`
Expected: AttributeError or ImportError on `MusicState`.

- [ ] **Step 3: Add `MusicState` + initial value**

Edit `backend/app/world.py`. Near the top (after imports, before `_LIGHTING_PRESETS`), add:

```python
from dataclasses import dataclass


@dataclass
class MusicState:
    track_id: str | None = None
    playing: bool = False
    volume: int = 50
    since: float | None = None

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "playing": self.playing,
            "volume": self.volume,
            "since": self.since,
        }
```

In `PartyWorld.__init__`, after the line `self.lighting: str = "day"`, add:

```python
        self.music: MusicState = MusicState()
```

In `PartyWorld.snapshot`, modify the return dict to include `"music": self.music.to_dict()`:

```python
        return {
            "participants": [
                self._participant_dict(p) for p in self.participants.values()
            ],
            "cursor": self.cursor,
            "lighting": self.lighting,
            "music": self.music.to_dict(),
            "modules": [self._module_snapshot(m) for m in placed],
            "active_reactions": active_reactions,
        }
```

- [ ] **Step 4: Verify pass**

Run: `cd backend && pytest tests/test_music_world.py -x --tb=short`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/world.py backend/tests/test_music_world.py
git commit -m "feat(music): add MusicState to PartyWorld and expose in snapshot"
```

---

## Task 4: `PartyWorld.set_music` action handler

**Files:**
- Modify: `backend/app/world.py`
- Modify: `backend/tests/test_music_world.py`

- [ ] **Step 1: Write failing tests for each action**

Append to `backend/tests/test_music_world.py`:

```python
import pytest
from app.events import MusicChangedEvent, Participant
from app.world import ParticipantNotInPartyError
from app.validation import MusicValidationError


def _join(w: PartyWorld, pid: str = "p1", kind: str = "agent") -> Participant:
    p = Participant(
        id=pid, kind=kind, username="U", color="#ff6b9d",
        x=10.0, y=10.0, joined_at=0.0,
    )
    w.join(p)
    return p


def test_play_sets_track_and_emits_event():
    w = _make_world()
    _join(w)
    ev = w.set_music("p1", action="play", track_id="lofi-loop")
    assert isinstance(ev, MusicChangedEvent)
    assert ev.track_id == "lofi-loop"
    assert ev.playing is True
    assert ev.volume == 50
    assert ev.actor_id == "p1"
    assert ev.actor_username == "U"
    assert ev.actor_kind == "agent"
    assert ev.room_wide is True
    assert w.music.track_id == "lofi-loop"
    assert w.music.playing is True
    assert w.music.since == ev.at


def test_pause_keeps_track_clears_playing():
    w = _make_world()
    _join(w)
    w.set_music("p1", action="play", track_id="lofi-loop")
    ev = w.set_music("p1", action="pause", track_id="lofi-loop")
    assert ev.playing is False
    assert ev.track_id == "lofi-loop"
    assert w.music.playing is False
    assert w.music.track_id == "lofi-loop"


def test_skip_switches_track_and_keeps_playing():
    w = _make_world()
    _join(w)
    w.set_music("p1", action="play", track_id="lofi-loop")
    ev = w.set_music("p1", action="skip", track_id="party-mix")
    assert ev.track_id == "party-mix"
    assert ev.playing is True
    assert w.music.track_id == "party-mix"


def test_set_volume_only_changes_volume():
    w = _make_world()
    _join(w)
    w.set_music("p1", action="play", track_id="lofi-loop")
    ev = w.set_music("p1", action="set_volume", track_id="lofi-loop", volume=10)
    assert ev.volume == 10
    assert ev.track_id == "lofi-loop"
    assert ev.playing is True
    assert w.music.volume == 10


def test_set_volume_requires_volume_argument():
    w = _make_world()
    _join(w)
    with pytest.raises(MusicValidationError):
        w.set_music("p1", action="set_volume", track_id="lofi-loop")


def test_unknown_track_raises():
    w = _make_world()
    _join(w)
    with pytest.raises(MusicValidationError):
        w.set_music("p1", action="play", track_id="rickroll")


def test_out_of_range_volume_raises():
    w = _make_world()
    _join(w)
    with pytest.raises(MusicValidationError):
        w.set_music("p1", action="play", track_id="lofi-loop", volume=999)


def test_non_participant_raises():
    w = _make_world()
    with pytest.raises(ParticipantNotInPartyError):
        w.set_music("ghost", action="play", track_id="lofi-loop")


def test_event_appended_and_seq_increments():
    w = _make_world()
    _join(w)
    seq_before = w.cursor
    ev = w.set_music("p1", action="play", track_id="lofi-loop")
    assert ev.seq == seq_before + 1
    assert w.cursor == seq_before + 1
```

- [ ] **Step 2: Watch fail**

Run: `cd backend && pytest tests/test_music_world.py -x --tb=short`
Expected: AttributeError `set_music`.

- [ ] **Step 3: Implement `set_music` on `PartyWorld`**

In `backend/app/world.py`, add to imports at top:

```python
from app.events import (
    ...
    MusicChangedEvent,
)
```

And add to the existing validation import block:

```python
from app.validation import (
    ...
    MusicValidationError,
    validate_music_action,
    validate_music_track,
    validate_music_volume,
)
```

Add the method right after `set_lighting`:

```python
    def set_music(
        self,
        changed_by: str,
        *,
        action: str,
        track_id: str,
        volume: int | None = None,
    ) -> MusicChangedEvent:
        if changed_by not in self.participants:
            raise ParticipantNotInPartyError(changed_by)
        a = validate_music_action(action)
        t = validate_music_track(track_id)
        now = time.time()

        if a == "play":
            new_playing = True
            new_track = t
            new_volume = (
                validate_music_volume(volume)
                if volume is not None else self.music.volume
            )
        elif a == "pause":
            new_playing = False
            new_track = t
            new_volume = self.music.volume
        elif a == "skip":
            new_playing = True
            new_track = t
            new_volume = self.music.volume
        elif a == "set_volume":
            if volume is None:
                raise MusicValidationError(
                    "volume is required for action 'set_volume'"
                )
            new_playing = self.music.playing
            new_track = t
            new_volume = validate_music_volume(volume)
        else:
            # validate_music_action already excluded this path.
            raise MusicValidationError(f"unknown action {a!r}")

        self.music = MusicState(
            track_id=new_track,
            playing=new_playing,
            volume=new_volume,
            since=now,
        )
        ev = MusicChangedEvent(
            seq=self._next_seq(),
            track_id=new_track,
            playing=new_playing,
            volume=new_volume,
            at=now,
            room_wide=True,
            **self._actor_fields(changed_by),
        )
        self._events.append(ev)
        self._emit(ev)
        return ev
```

- [ ] **Step 4: Verify pass**

Run: `cd backend && pytest tests/test_music_world.py -x --tb=short`
Expected: all 12 tests green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/world.py backend/tests/test_music_world.py
git commit -m "feat(music): implement PartyWorld.set_music with play/pause/skip/set_volume"
```

---

## Task 5: Route handler (no rate-limit yet)

**Files:**
- Create: `backend/app/routes/music.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_music_route.py`

- [ ] **Step 1: Failing route tests**

Create `backend/tests/test_music_route.py`:

```python
def test_music_play_returns_state(client, register_human, join_party):
    user = register_human(username="DJ", color="#ff6b9d")
    join_party(user, slug="cream-terrazzo")
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["music"]["track_id"] == "lofi-loop"
    assert body["music"]["playing"] is True
    assert body["music"]["volume"] == 50
    assert "cursor" in body


def test_music_set_volume(client, register_human, join_party):
    user = register_human(username="DJ", color="#ff6b9d")
    join_party(user, slug="cream-terrazzo")
    client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "set_volume",
            "track_id": "lofi-loop",
            "volume": 10,
        },
    )
    assert r.status_code == 200
    assert r.json()["music"]["volume"] == 10


def test_music_unknown_track_422_with_allowed_list(
    client, register_human, join_party
):
    user = register_human(username="DJ", color="#ff6b9d")
    join_party(user, slug="cream-terrazzo")
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "play",
            "track_id": "rickroll",
        },
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_track"
    assert "allowed_tracks" in detail
    assert "lofi-loop" in detail["allowed_tracks"]


def test_music_bad_volume_422(client, register_human, join_party):
    user = register_human(username="DJ", color="#ff6b9d")
    join_party(user, slug="cream-terrazzo")
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "set_volume",
            "track_id": "lofi-loop",
            "volume": 500,
        },
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_volume"


def test_music_not_in_party_409(client, register_human):
    user = register_human(username="DJ", color="#ff6b9d")
    # NOT joined
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    assert r.status_code == 409


def test_music_unknown_party_404(client, register_human):
    user = register_human(username="DJ", color="#ff6b9d")
    r = client.post(
        "/api/parties/no-such-party/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    assert r.status_code == 404


def test_music_bad_action_422(client, register_human, join_party):
    user = register_human(username="DJ", color="#ff6b9d")
    join_party(user, slug="cream-terrazzo")
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "nuke",
            "track_id": "lofi-loop",
        },
    )
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "invalid_action"
```

- [ ] **Step 2: Watch fail**

Run: `cd backend && pytest tests/test_music_route.py -x --tb=short`
Expected: 404 on every test (route not mounted).

- [ ] **Step 3: Implement the route**

Create `backend/app/routes/music.py`:

```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import (
    INVALID_ACTION,
    INVALID_TRACK,
    INVALID_VOLUME,
    NOT_IN_PARTY,
    envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import (
    MUSIC_TRACK_ALLOWLIST,
    MusicValidationError,
)
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail="party not found")
    return world


class MusicRequest(BaseModel):
    principal: Principal
    track_id: str
    action: Literal["play", "pause", "skip", "set_volume"]
    volume: int | None = None


_SLUG_PATTERN = r"^[a-z0-9-]+$"


def _classify_error(exc: MusicValidationError) -> tuple[str, dict]:
    msg = str(exc)
    if "track" in msg:
        return INVALID_TRACK, {"allowed_tracks": list(MUSIC_TRACK_ALLOWLIST)}
    if "volume" in msg:
        return INVALID_VOLUME, {}
    if "action" in msg:
        return INVALID_ACTION, {}
    return INVALID_ACTION, {}


@router.post("/{slug}/music")
def set_music(
    body: MusicRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.set_music(
            resolved.id,
            action=body.action,
            track_id=body.track_id,
            volume=body.volume,
        )
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except MusicValidationError as exc:
        code, extras = _classify_error(exc)
        raise HTTPException(
            status_code=422,
            detail=envelope(code, message=str(exc), **extras),
        )
    return {
        "music": {
            "track_id": ev.track_id,
            "playing": ev.playing,
            "volume": ev.volume,
            "since": ev.at,
        },
        "cursor": world.cursor,
    }
```

Wire the router in `backend/app/main.py`. Add to the imports near the other `from app.routes import ...` lines:

```python
from app.routes import music as music_routes
```

After the existing `app.dependency_overrides[lighting_routes._store_dep] = get_store` line, add:

```python
app.dependency_overrides[music_routes._store_dep] = get_store
```

And after `app.include_router(lighting_routes.router)` add:

```python
app.include_router(music_routes.router)
```

- [ ] **Step 4: Verify pass**

Run: `cd backend && pytest tests/test_music_route.py -x --tb=short`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/music.py backend/app/main.py backend/tests/test_music_route.py
git commit -m "feat(music): add POST /api/parties/{slug}/music endpoint"
```

---

## Task 6: Cooldown via spec #03 rate-limit module

**Assumes:** spec #03 has shipped `backend/app/rate_limit.py` exporting:
- `acquire(scope: str, principal_id: str, *, burst: int, refill_per_sec: float) -> bool` — returns `False` when bucket empty.
- `RateLimited` exception (used by some scopes); we don't need to raise it here — checking the `bool` return is enough.

If spec #03 chose a slightly different name (e.g. `consume`), use the actual exported symbol — do not redefine the module.

**Files:**
- Modify: `backend/app/routes/music.py`
- Modify: `backend/tests/test_music_route.py`

- [ ] **Step 1: Add failing test for cooldown**

Append to `backend/tests/test_music_route.py`:

```python
import time


def test_music_burst_two_then_429(client, register_human, join_party, monkeypatch):
    user = register_human(username="DJ", color="#ff6b9d")
    join_party(user, slug="cream-terrazzo")

    # Reset rate-limit state for a clean window.
    from app import rate_limit
    rate_limit._buckets.clear()  # type: ignore[attr-defined]

    payload = {
        "principal": {"kind": "human", "session_id": user["session_id"]},
        "action": "play",
        "track_id": "lofi-loop",
    }
    r1 = client.post("/api/parties/cream-terrazzo/music", json=payload)
    r2 = client.post("/api/parties/cream-terrazzo/music", json=payload)
    r3 = client.post("/api/parties/cream-terrazzo/music", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["detail"]["error"] == "rate_limited_music"


def test_music_refill_after_five_seconds(
    client, register_human, join_party, monkeypatch
):
    user = register_human(username="DJ", color="#ff6b9d")
    join_party(user, slug="cream-terrazzo")

    from app import rate_limit
    rate_limit._buckets.clear()  # type: ignore[attr-defined]

    fake_now = [1000.0]

    def fake_time() -> float:
        return fake_now[0]

    monkeypatch.setattr(rate_limit, "_now", fake_time)

    payload = {
        "principal": {"kind": "human", "session_id": user["session_id"]},
        "action": "play",
        "track_id": "lofi-loop",
    }
    client.post("/api/parties/cream-terrazzo/music", json=payload)
    client.post("/api/parties/cream-terrazzo/music", json=payload)
    r3 = client.post("/api/parties/cream-terrazzo/music", json=payload)
    assert r3.status_code == 429

    # 5 seconds later: bucket refills 1 unit.
    fake_now[0] += 5.0
    r4 = client.post("/api/parties/cream-terrazzo/music", json=payload)
    assert r4.status_code == 200
```

> **Implementation note:** If spec #03's bucket store is keyed differently (e.g. stored on `Store` instead of a module-level dict), update the `_buckets.clear()` line to match. The behavior under test (burst=2, refill 1 / 5s, scope `"music"`) is what matters.

- [ ] **Step 2: Watch fail**

Run: `cd backend && pytest tests/test_music_route.py::test_music_burst_two_then_429 -x --tb=short`
Expected: third call returns 200 (no cooldown wired yet).

- [ ] **Step 3: Wire cooldown into the route**

Edit `backend/app/routes/music.py`. Add to imports:

```python
from app import rate_limit
from app.errors import RATE_LIMITED_MUSIC
```

In `set_music`, immediately after `resolved = resolve_principal(...)` and BEFORE the `try:` block, add:

```python
    allowed = rate_limit.acquire(
        scope="music",
        principal_id=resolved.id,
        burst=2,
        refill_per_sec=0.2,  # 1 token per 5 seconds
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                RATE_LIMITED_MUSIC,
                message="music cooldown: burst 2, refill 1 per 5s",
            ),
        )
```

- [ ] **Step 4: Verify pass**

Run: `cd backend && pytest tests/test_music_route.py -x --tb=short`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/music.py backend/tests/test_music_route.py
git commit -m "feat(music): apply token-bucket cooldown (burst 2, refill 1/5s)"
```

---

## Task 7: `/observe` exposes live music state (replace hard-coded label)

**Files:**
- Modify: `backend/app/routes/party_actions.py`
- Modify: `backend/tests/test_observe_route.py`

- [ ] **Step 1: Update the existing observe test**

Open `backend/tests/test_observe_route.py` and replace the line:

```python
    assert body["room"]["music"] == "Music coming soon"
```

with:

```python
    assert body["music"] == {
        "track_id": None,
        "playing": False,
        "volume": 50,
        "since": None,
    }
    # The static label remains in room.music for backwards compatibility.
    assert body["room"]["music"] == "Music coming soon"
```

Then add a new test at the end of the file:

```python
def test_observe_reflects_music_play(client, register_human, join_party):
    user = register_human(username="DJ", color="#ff6b9d")
    join_party(user, slug="cream-terrazzo")
    client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "session_id": user["session_id"]},
            "action": "play",
            "track_id": "lofi-loop",
        },
    )
    r = client.get("/api/parties/cream-terrazzo/observe")
    assert r.status_code == 200
    body = r.json()
    assert body["music"]["track_id"] == "lofi-loop"
    assert body["music"]["playing"] is True
    assert body["music"]["volume"] == 50
    assert isinstance(body["music"]["since"], float)
```

- [ ] **Step 2: Watch fail**

Run: `cd backend && pytest tests/test_observe_route.py -x --tb=short`
Expected: second test fails (no top-level `music` key).

- [ ] **Step 3: Wire music into `/observe`**

Edit `backend/app/routes/party_actions.py`. In the `observe` handler initial-snapshot branch, add `"music": snap["music"]` to the returned dict:

```python
    if since is None:
        snap = world.snapshot()
        return {
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
            "modules": snap["modules"],
            "lighting": snap["lighting"],
            "music": snap["music"],
            "active_reactions": snap["active_reactions"],
            "recent_chat": world.recent_chat(),
        }
    return world.observe_since(since)
```

Do **not** modify `_room_view` — the static `party.music.label` is independent backwards-compat data displayed in the existing `MusicPill`. The new live state lives at the top-level `music` key, mirroring `lighting`.

- [ ] **Step 4: Verify pass**

Run: `cd backend && pytest tests/test_observe_route.py tests/test_music_route.py tests/test_music_world.py -x --tb=short`
Expected: all green.

- [ ] **Step 5: Run the full backend test suite to catch regressions**

Run: `cd backend && pytest -x --tb=short`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/party_actions.py backend/tests/test_observe_route.py
git commit -m "feat(music): expose live music state in /observe snapshot"
```

---

## Task 8: Agent guide entry

**Files:**
- Modify: `backend/app/routes/agent_guide.py`

- [ ] **Step 1: Read the section that needs editing**

Open `backend/app/routes/agent_guide.py`. Find the `## Modules` section (line ~226). The `lighting` bullet currently reads:

```
- **Room-level** (no footprint): `lighting`. Anyone in the party can change
  the preset via `POST /api/parties/{{slug}}/lighting`.
```

- [ ] **Step 2: Add music documentation**

Replace that bullet with:

```
- **Room-level** (no footprint):
  - `lighting` — anyone in the party can change the preset via
    `POST /api/parties/{{slug}}/lighting`.
  - `music` — control the room soundtrack via
    `POST /api/parties/{{slug}}/music` with
    `{{principal, track_id, action, volume?}}`.
    - `action` is one of `play`, `pause`, `skip`, `set_volume`.
    - `track_id` must be one of the allow-list:
      `lofi-loop`, `jazz-club`, `synthwave`, `ambient-1`, `party-mix`.
      Unknown tracks return `422 invalid_track` with `allowed_tracks` in the envelope.
    - `volume` is an integer 0-100; required for `set_volume`, optional otherwise.
      Out of range returns `422 invalid_volume`.
    - Emits a `music_changed` event with `actor_id`, `actor_username`,
      `actor_kind`, `track_id`, `playing`, `volume`, `at`, `room_wide: true`.
    - **Cooldown:** token bucket, burst 2, refill 1 token per 5 seconds,
      keyed per-principal in scope `"music"`. Exceeding it returns
      `429 rate_limited_music`.
    - The current music state appears in the initial `/observe` response at
      the top-level `music` field:
      `{{track_id, playing, volume, since}}` (mirrors `lighting`).
```

- [ ] **Step 3: Smoke-test the guide route**

Run: `cd backend && pytest tests/test_agent_guide_route.py -x --tb=short` (if that file exists).
If no such test exists, manually hit the route:

```bash
cd backend && python -c "from fastapi.testclient import TestClient; from app.main import app; print(TestClient(app).get('/api/agent-guide').text[:500])"
```

Expected: no 500, body contains the substring `POST /api/parties/{slug}/music`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/agent_guide.py
git commit -m "docs(music): document /music endpoint, allow-list, event, cooldown in agent guide"
```

---

## Task 9: Frontend types

**Files:**
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Add types**

Append to `frontend/src/api/types.ts` (after existing exports):

```typescript
export type MusicTrackId =
  | 'lofi-loop'
  | 'jazz-club'
  | 'synthwave'
  | 'ambient-1'
  | 'party-mix';

export const MUSIC_TRACK_IDS: ReadonlyArray<MusicTrackId> = [
  'lofi-loop',
  'jazz-club',
  'synthwave',
  'ambient-1',
  'party-mix',
];

export type MusicAction = 'play' | 'pause' | 'skip' | 'set_volume';

export type MusicState = {
  track_id: MusicTrackId | null;
  playing: boolean;
  volume: number;
  since: number | null;
};

export type MusicChangedEvent = {
  type: 'music_changed';
  seq: number;
  track_id: MusicTrackId;
  playing: boolean;
  volume: number;
  at: number;
  actor_id: string | null;
  actor_username: string | null;
  actor_kind: 'human' | 'agent' | null;
  room_wide: true;
};
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts
git commit -m "feat(music): add MusicState/MusicChangedEvent/MusicTrackId types"
```

---

## Task 10: `MusicPill` shows live track ID when present

**Files:**
- Modify: `frontend/src/components/MusicPill.tsx`
- Modify: `frontend/src/components/PartySpace.tsx`
- Create: `frontend/tests/MusicPill.test.tsx`

- [ ] **Step 1: Write failing component test**

Create `frontend/tests/MusicPill.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import MusicPill from '../src/components/MusicPill';

describe('MusicPill', () => {
  it('renders fallback label when no trackId provided', () => {
    render(<MusicPill label="Music coming soon" />);
    expect(screen.getByText(/Music coming soon/)).toBeInTheDocument();
  });

  it('renders the trackId when provided', () => {
    render(<MusicPill label="Music coming soon" trackId="lofi-loop" />);
    expect(screen.getByText(/lofi-loop/)).toBeInTheDocument();
  });

  it('renders the fallback label when trackId is null', () => {
    render(<MusicPill label="Music coming soon" trackId={null} />);
    expect(screen.getByText(/Music coming soon/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Watch fail**

Run: `cd frontend && npm test -- --run MusicPill`
Expected: TypeScript error or failure — `trackId` prop unknown.

- [ ] **Step 3: Update `MusicPill`**

Replace the entire body of `frontend/src/components/MusicPill.tsx`:

```typescript
type Props = {
  label: string;
  trackId?: string | null;
};

export default function MusicPill({ label, trackId }: Props) {
  const display = trackId ? trackId : label;
  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        right: 12,
        padding: '4px 10px',
        background: 'rgba(0,0,0,0.6)',
        color: '#fff',
        borderRadius: 999,
        fontSize: 12,
      }}
    >
      🎵 {display}
    </div>
  );
}
```

- [ ] **Step 4: Wire live `music.track_id` through `PartySpace`**

Open `frontend/src/components/PartySpace.tsx`. Find the line `<MusicPill label={party.music.label} />` (around line 272).

If `PartySpace` already accepts/derives the observe payload's `music` field, replace with:

```tsx
<MusicPill
  label={party.music.label}
  trackId={music?.track_id ?? null}
/>
```

…where `music` is the value from the latest `/observe` response. If the component does not yet receive this, locate the parent that fetches `/observe` and thread a `music?: MusicState` prop down to `PartySpace`. Add the prop to its signature:

```tsx
import type { MusicState } from '../api/types';

type PartySpaceProps = {
  // ...existing props
  music?: MusicState | null;
};

export default function PartySpace({ /* existing props */ music }: PartySpaceProps) {
  // ...
}
```

> **Discovery step:** before editing, run `grep -n "PartySpace" frontend/src --include="*.tsx" -r` to find every call site so the new optional prop doesn't break callers. Because the prop is optional with a default of `undefined`, no existing call site needs changes.

- [ ] **Step 5: Verify component and full frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: all tests pass. Existing tests that hard-code `music: { url: null, label: 'Music coming soon' }` continue passing because `trackId` is undefined → falls back to `label`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/MusicPill.tsx frontend/src/components/PartySpace.tsx frontend/tests/MusicPill.test.tsx
git commit -m "feat(music): display live track_id in MusicPill when present"
```

---

## Task 11: Smoke test end-to-end

**Files:** none — exploratory.

- [ ] **Step 1: Start the backend**

```bash
cd backend && uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Register a session, join, then drive the endpoint**

In a second terminal:

```bash
SESSION=$(curl -s -X POST http://localhost:8000/api/session -H 'content-type: application/json' \
  -d '{"username":"DJ","color":"#ff6b9d"}' | python -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

curl -s -X POST http://localhost:8000/api/parties/cream-terrazzo/join -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"human\",\"session_id\":\"$SESSION\"}}"

curl -s -X POST http://localhost:8000/api/parties/cream-terrazzo/music -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"human\",\"session_id\":\"$SESSION\"},\"action\":\"play\",\"track_id\":\"lofi-loop\"}"

curl -s http://localhost:8000/api/parties/cream-terrazzo/observe | python -m json.tool | grep -A4 '"music"'
```

Expected: the final `observe` call shows
```
"music": {
    "track_id": "lofi-loop",
    "playing": true,
    "volume": 50,
    "since": <timestamp>
}
```

- [ ] **Step 3: Verify burst+cooldown manually**

Run three identical `set_volume` requests in <5s:

```bash
for i in 1 2 3; do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/api/parties/cream-terrazzo/music \
    -H 'content-type: application/json' \
    -d "{\"principal\":{\"kind\":\"human\",\"session_id\":\"$SESSION\"},\"action\":\"set_volume\",\"track_id\":\"lofi-loop\",\"volume\":$((20+i))}"
done
```

Expected: `200`, `200`, `429`.

- [ ] **Step 4: Verify unknown-track envelope**

```bash
curl -s -X POST http://localhost:8000/api/parties/cream-terrazzo/music \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"human\",\"session_id\":\"$SESSION\"},\"action\":\"play\",\"track_id\":\"rickroll\"}" | python -m json.tool
```

Expected:
```
"detail": {
    "error": "invalid_track",
    "message": "...",
    "allowed_tracks": ["lofi-loop", "jazz-club", "synthwave", "ambient-1", "party-mix"]
}
```

No commit — this is a manual verification step.

---

## Out of scope (do not implement in this plan)

- **Audio playback in the frontend.** The `MusicPill` shows the track ID only; no `<audio>` element, no buffering, no DJ controls.
- **Track metadata.** No title/artist/duration — track IDs are opaque strings.
- **Persistence across server restarts.** Music state is in-memory like `lighting`.
- **Per-zone or proximity-scoped music.** All music events are `room_wide=True`.
- **Modifications to lighting.** Lighting already exists and is untouched.
- **Forking spec #03's rate-limit module.** This plan reuses `app.rate_limit.acquire` with scope `"music"`; do not copy or reimplement the bucket.

## Self-review notes

- Every spec requirement (1-9) maps to at least one task in the spec→task table.
- Event uses unified actor shape (`actor_id`, `actor_username`, `actor_kind`) per spec #01.
- All 422 responses use the `envelope(code, message=..., **extras)` shape from spec #01.
- `MusicChangedEvent.room_wide` defaults to `True` and is always set so explicitly in `set_music`.
- `MusicState`, `set_music`, `validate_music_track`, `validate_music_volume`, `validate_music_action`, `MUSIC_TRACK_ALLOWLIST`, `RATE_LIMITED_MUSIC`, `INVALID_TRACK`, `INVALID_VOLUME`, `INVALID_ACTION` — every symbol referenced in later tasks is defined in earlier tasks.
- No placeholders; every code-touching step shows the actual code.
