# Expressive Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement feature-backlog §2 ("Expressive Actions") — add `/gesture`, targeted `/react`, `/cosmetic`, and avatar facing direction so personas can express *intent* and *direction* without polluting the chat channel.

**Architecture:** Two new endpoints (`POST /api/parties/{slug}/gesture`, `POST /api/parties/{slug}/cosmetic`) introducing two new event types (`gesture`, `cosmetic`) following the spec #01 unified event shape. `/react` is extended with optional `target_seq` / `target_actor_id`. The `move` event and `Participant` model gain a derived `facing` direction computed from the (old → new) position delta. Cooldowns reuse spec #03's rate-limit module via two new scopes (`gesture`, `cosmetic`); chat buckets are untouched.

**Tech Stack:** FastAPI (Python 3.11), Pydantic v2, pytest + httpx for backend tests. TypeScript types in `frontend/src/api/types.ts` get additive optional fields (no UI behavior change in this plan).

---

## Spec → Task Map

| Spec point (feature-backlog §2) | Task |
|---|---|
| §2 P0 `/gesture` enum + endpoint | Tasks 2-4 |
| §2 P0 gesture cooldown bucket (burst 3, refill 1 / 2s) | Task 3 |
| §2 P1 targeted reactions (`target_seq` / `target_actor_id`) | Task 5 |
| §2 P2 room-wide cosmetic events (`/cosmetic`) | Tasks 6-7 |
| §2 P2 cosmetic cooldown bucket (burst 1, refill 1 / 10s) | Task 7 |
| §2 P2 avatar facing direction | Task 8 |
| Agent guide update (gestures, cosmetics, facing, targeted reactions) | Task 9 |
| Frontend type sync | Task 9 |
| Final verification + CLAUDE.md | Task 10 |

**Coordination assumptions (do NOT redesign):**
- Spec #01 landed: unified event shape — `actor_id`, `actor_username`, `actor_kind` flat at top level; standardized error envelope `{"detail": {"error": "<code>", "message": "...", ...extra}}`; new event types use the unified shape.
- Spec #02 landed: `PROXIMITY_RADIUS` constant in `world.py`, scoped `/observe`, `room_wide: bool` flag on event payloads (default `False`). Gestures and reactions are proximity-scoped (default). Cosmetics set `room_wide=True`.
- Spec #03 landed: a rate-limit module (assume `backend/app/rate_limit.py` exposing `TokenBucketRegistry` keyed by `(scope: str, actor_id: str)` with a `try_consume(scope, actor_id) -> ConsumeResult` API that returns `ok: bool, retry_after_ms: int`). New scopes `gesture` and `cosmetic` are registered alongside the existing `chat` scope.
- Out of scope: chat (#03), modules (#04), follow / proposal / `actor_color` (#06).

---

## File Structure

**Backend — create:**
- `backend/app/routes/expressive.py` — new router with `/gesture` and `/cosmetic` endpoints (kept separate from `reactions.py` to avoid bloating that file; mounted in `app/main.py`).
- `backend/tests/test_gesture_route.py` — gesture endpoint behavior.
- `backend/tests/test_gesture_cooldown.py` — gesture rate-limit bucket integration.
- `backend/tests/test_react_targeted.py` — targeted reaction behavior.
- `backend/tests/test_cosmetic_route.py` — cosmetic endpoint behavior + cooldown.
- `backend/tests/test_move_facing.py` — facing direction derivation.

**Backend — modify:**
- `backend/app/validation.py` — add `ALLOWED_GESTURES`, `ALLOWED_COSMETIC_EFFECTS`, `GESTURE_TTL_SECONDS`, `COSMETIC_TTL_SECONDS`, `GestureValidationError`, `CosmeticValidationError`, `validate_gesture`, `validate_cosmetic_effect`.
- `backend/app/events.py` — add `GestureEvent`, `CosmeticEvent`; add optional `target_seq` / `target_actor_id` to `ReactionEvent`; add `facing` to `MoveEvent` and `Participant`.
- `backend/app/world.py` — add `gesture()`, `cosmetic()` methods on `PartyWorld`; extend `react()` signature with `target_seq` / `target_actor_id`; compute `facing` inside `move()`; expose facing in `_participant_dict`.
- `backend/app/rate_limit.py` — register `gesture` and `cosmetic` scopes (spec #03 module; add scope constants here).
- `backend/app/routes/reactions.py` — accept and forward `target_seq` / `target_actor_id`; validate "at most one" and existence; return structured 422/404.
- `backend/app/routes/party_actions.py` — no behavior change in `/move` itself (facing is derived inside `world.move()`); however the `_participant_dict` projection used by `observe` exposes `facing`.
- `backend/app/routes/agent_guide.py` — new sections: "Gestures", "Cosmetics", "Targeted reactions", "Avatar facing".
- `backend/app/main.py` — mount the new `expressive` router.

**Frontend — modify:**
- `frontend/src/api/types.ts` — add `GestureEvent`, `CosmeticEvent`; add `target_seq?` / `target_actor_id?` to `ReactionEvent`; add `facing?` to `MoveEvent` and `Participant`.

---

## Task 1: Pre-flight — confirm baseline

**Files:** none (read-only)

- [ ] **Step 1: Run backend test suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS on the current branch (specs #01, #02, #03 assumed merged).

- [ ] **Step 2: Run frontend test suite**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS.

- [ ] **Step 3: Confirm spec #03's rate-limit module is importable**

Run: `cd backend && python -c "from app.rate_limit import TokenBucketRegistry, RateLimitScope; print('ok')"`
Expected: prints `ok`. If this import fails, spec #03 has not landed — STOP and report; do not invent a rate-limit module here.

---

## Task 2: Validation constants + helpers

**Files:**
- Modify: `backend/app/validation.py`
- Test: `backend/tests/test_validation_expressive.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_validation_expressive.py`:

```python
import pytest

from app.validation import (
    ALLOWED_COSMETIC_EFFECTS,
    ALLOWED_GESTURES,
    COSMETIC_TTL_SECONDS,
    CosmeticValidationError,
    GESTURE_TTL_SECONDS,
    GestureValidationError,
    validate_cosmetic_effect,
    validate_gesture,
)


def test_allowed_gestures_exact_set():
    assert ALLOWED_GESTURES == (
        "wave", "point", "dance", "jump", "sit", "shiver", "bow", "nod",
    )


def test_allowed_cosmetic_effects_exact_set():
    assert ALLOWED_COSMETIC_EFFECTS == (
        "confetti", "sparkle", "lights_flash", "ping",
    )


def test_gesture_ttl_default_two_seconds():
    assert GESTURE_TTL_SECONDS == 2.0


def test_cosmetic_ttl_default_three_seconds():
    assert COSMETIC_TTL_SECONDS == 3.0


def test_validate_gesture_accepts_each():
    for g in ALLOWED_GESTURES:
        assert validate_gesture(g) == g


def test_validate_gesture_rejects_unknown():
    with pytest.raises(GestureValidationError):
        validate_gesture("twerk")


def test_validate_gesture_rejects_empty():
    with pytest.raises(GestureValidationError):
        validate_gesture("")


def test_validate_cosmetic_accepts_each():
    for e in ALLOWED_COSMETIC_EFFECTS:
        assert validate_cosmetic_effect(e) == e


def test_validate_cosmetic_rejects_unknown():
    with pytest.raises(CosmeticValidationError):
        validate_cosmetic_effect("rain")
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_validation_expressive.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement the constants and validators**

Append to `backend/app/validation.py` (after the existing `validate_stroke`):

```python
ALLOWED_GESTURES: tuple[str, ...] = (
    "wave", "point", "dance", "jump", "sit", "shiver", "bow", "nod",
)

ALLOWED_COSMETIC_EFFECTS: tuple[str, ...] = (
    "confetti", "sparkle", "lights_flash", "ping",
)

GESTURE_TTL_SECONDS = 2.0
COSMETIC_TTL_SECONDS = 3.0


class GestureValidationError(ValueError):
    pass


class CosmeticValidationError(ValueError):
    pass


def validate_gesture(gesture: str) -> str:
    if gesture not in ALLOWED_GESTURES:
        raise GestureValidationError(f"gesture {gesture!r} not in allow-list")
    return gesture


def validate_cosmetic_effect(effect: str) -> str:
    if effect not in ALLOWED_COSMETIC_EFFECTS:
        raise CosmeticValidationError(f"effect {effect!r} not in allow-list")
    return effect
```

- [ ] **Step 4: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_validation_expressive.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/validation.py backend/tests/test_validation_expressive.py
git commit -m "feat(validation): add gesture + cosmetic allow-lists and validators"
```

---

## Task 3: Register `gesture` + `cosmetic` rate-limit scopes

**Files:**
- Modify: `backend/app/rate_limit.py`
- Test: `backend/tests/test_rate_limit_expressive_scopes.py` (new)

This task assumes spec #03's `rate_limit.py` exposes:

```python
class RateLimitScope(StrEnum):
    CHAT = "chat"
    # ...

# A registry-style API used by spec #03's chat route:
class TokenBucketRegistry:
    def configure(self, scope: str, *, burst: int, refill_per_second: float) -> None: ...
    def try_consume(self, scope: str, actor_id: str) -> "ConsumeResult": ...

class ConsumeResult:
    ok: bool
    retry_after_ms: int
```

If the exact API differs, ADAPT the calls in Tasks 4 and 7 to match — do not change spec #03's module shape; the integration test in Task 3 step 3 below pins the actual contract.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_rate_limit_expressive_scopes.py`:

```python
from app.rate_limit import RateLimitScope, TokenBucketRegistry


def test_gesture_scope_exists():
    assert RateLimitScope.GESTURE.value == "gesture"


def test_cosmetic_scope_exists():
    assert RateLimitScope.COSMETIC.value == "cosmetic"


def test_gesture_default_config_burst_3_refill_one_per_two_seconds():
    reg = TokenBucketRegistry()
    reg.configure_defaults()  # spec #03 helper that registers all known scopes
    # 3 consumes should succeed back-to-back.
    for _ in range(3):
        res = reg.try_consume(RateLimitScope.GESTURE.value, actor_id="alice")
        assert res.ok
    # 4th immediately is denied.
    denied = reg.try_consume(RateLimitScope.GESTURE.value, actor_id="alice")
    assert not denied.ok
    # retry_after_ms is positive and <= 2000 (refill 1 per 2s).
    assert 0 < denied.retry_after_ms <= 2000


def test_cosmetic_default_config_burst_1_refill_one_per_ten_seconds():
    reg = TokenBucketRegistry()
    reg.configure_defaults()
    res = reg.try_consume(RateLimitScope.COSMETIC.value, actor_id="alice")
    assert res.ok
    denied = reg.try_consume(RateLimitScope.COSMETIC.value, actor_id="alice")
    assert not denied.ok
    assert 0 < denied.retry_after_ms <= 10_000


def test_buckets_are_independent_per_actor():
    reg = TokenBucketRegistry()
    reg.configure_defaults()
    reg.try_consume(RateLimitScope.COSMETIC.value, actor_id="alice")
    bob = reg.try_consume(RateLimitScope.COSMETIC.value, actor_id="bob")
    assert bob.ok


def test_gesture_bucket_independent_from_chat_bucket():
    reg = TokenBucketRegistry()
    reg.configure_defaults()
    # Drain gesture bucket.
    for _ in range(3):
        reg.try_consume(RateLimitScope.GESTURE.value, actor_id="alice")
    # Chat is still available.
    chat_res = reg.try_consume(RateLimitScope.CHAT.value, actor_id="alice")
    assert chat_res.ok
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_rate_limit_expressive_scopes.py -v`
Expected: FAIL — `GESTURE`/`COSMETIC` scope missing.

- [ ] **Step 3: Add the new scopes to spec #03's rate-limit module**

In `backend/app/rate_limit.py`:

```python
class RateLimitScope(StrEnum):
    CHAT = "chat"
    GESTURE = "gesture"
    COSMETIC = "cosmetic"
```

…and extend `configure_defaults` (spec #03's helper that the app calls at startup) to register the two new buckets without touching the chat config:

```python
def configure_defaults(self) -> None:
    # ...existing chat config left untouched...
    self.configure(
        RateLimitScope.GESTURE.value,
        burst=3,
        refill_per_second=0.5,  # 1 token per 2 seconds
    )
    self.configure(
        RateLimitScope.COSMETIC.value,
        burst=1,
        refill_per_second=0.1,  # 1 token per 10 seconds
    )
```

If `configure_defaults` does not yet exist (i.e. spec #03 named the helper differently), ADD this helper and call it from wherever the app initializes the registry — but keep the chat config delegating to spec #03's existing setup; do not duplicate it.

- [ ] **Step 4: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_rate_limit_expressive_scopes.py -v`
Expected: PASS.

- [ ] **Step 5: Run full backend suite (spec #03 chat tests must still pass)**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/rate_limit.py backend/tests/test_rate_limit_expressive_scopes.py
git commit -m "feat(rate-limit): register gesture + cosmetic scopes (burst 3/0.5Hz, 1/0.1Hz)"
```

---

## Task 4: `GestureEvent` model + `world.gesture()`

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/world.py`
- Test: `backend/tests/test_world_gesture.py` (new)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_world_gesture.py`:

```python
import pytest

from app.events import GestureEvent, Participant
from app.models import PartyConfig, Room, WorldSize
from app.validation import GESTURE_TTL_SECONDS, GestureValidationError
from app.world import ParticipantNotInPartyError, PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t", name="t",
        worldSize=WorldSize(width=800, height=600),
        room=Room(walls=[]),
        zones=[], modules=[],
    )
    return PartyWorld(party=party)


def _join(w: PartyWorld, pid: str = "p1") -> Participant:
    p = Participant(
        id=pid, kind="human", username="Alice", color="#ff6b9d",
        x=100.0, y=100.0, joined_at=0.0,
    )
    w.join(p)
    return p


def test_gesture_emits_event_with_actor_fields():
    w = _world()
    _join(w)
    ev = w.gesture("p1", "wave")
    assert isinstance(ev, GestureEvent)
    assert ev.gesture == "wave"
    assert ev.actor_id == "p1"
    assert ev.actor_username == "Alice"
    assert ev.actor_kind == "human"
    assert ev.expires_at == pytest.approx(ev.at + GESTURE_TTL_SECONDS, abs=0.05)


def test_gesture_event_room_wide_false_default():
    w = _world()
    _join(w)
    ev = w.gesture("p1", "wave")
    assert ev.room_wide is False  # proximity-scoped


def test_gesture_unknown_raises_validation_error():
    w = _world()
    _join(w)
    with pytest.raises(GestureValidationError):
        w.gesture("p1", "twerk")


def test_gesture_unknown_participant_raises():
    w = _world()
    with pytest.raises(ParticipantNotInPartyError):
        w.gesture("ghost", "wave")


def test_gesture_uses_unified_seq_counter():
    w = _world()
    _join(w)  # seq 1
    ev1 = w.gesture("p1", "wave")
    ev2 = w.gesture("p1", "bow")
    assert ev2.seq == ev1.seq + 1
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_world_gesture.py -v`
Expected: FAIL — `GestureEvent` does not exist; `world.gesture` does not exist.

- [ ] **Step 3: Add `GestureEvent` to `events.py`**

In `backend/app/events.py`, add (after `ReactionEvent`):

```python
class GestureEvent(BaseModel):
    seq: int
    type: Literal["gesture"] = "gesture"
    gesture: str  # one of ALLOWED_GESTURES
    at: float
    expires_at: float
    room_wide: bool = False
    actor_id: str
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
```

…and add `GestureEvent` to the `Event` union at the bottom of the file:

```python
Event = (
    JoinEvent
    | LeaveEvent
    | MoveEvent
    | ChatEvent
    | ReactionEvent
    | GestureEvent
    | LightingChangedEvent
    | NoteCreatedEvent
    | NoteUpdatedEvent
    | NoteDeletedEvent
    | StrokeAddedEvent
    | StrokeDroppedEvent
    | BoardClearedEvent
    | VoteChangedEvent
)
```

- [ ] **Step 4: Add `gesture()` to `PartyWorld`**

In `backend/app/world.py`:

1. Add to the `from app.events import (...)` block: `GestureEvent`.
2. Add to the `from app.validation import (...)` block: `GESTURE_TTL_SECONDS`, `validate_gesture`.
3. Add the method (place near `react`):

```python
def gesture(self, participant_id: str, gesture: str) -> GestureEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    cleaned = validate_gesture(gesture)
    now = time.time()
    ev = GestureEvent(
        seq=self._next_seq(),
        gesture=cleaned,
        at=now,
        expires_at=now + GESTURE_TTL_SECONDS,
        room_wide=False,
        **self._actor_fields(participant_id),
    )
    self._events.append(ev)
    self._emit(ev)
    return ev
```

- [ ] **Step 5: Run, confirm pass**

Run: `cd backend && python -m pytest tests/test_world_gesture.py -v`
Expected: PASS.

- [ ] **Step 6: Run full backend suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS. (Spec #02's proximity-scoped observer should already gate `gesture` events the same way it gates `reaction` — if it filters by event type explicitly, add `"gesture"` to the proximity-scoped list. Check `backend/app/world.py:observe_since` after spec #02 lands.)

- [ ] **Step 7: Commit**

```bash
git add backend/app/events.py backend/app/world.py backend/tests/test_world_gesture.py
git commit -m "feat(world): add GestureEvent + PartyWorld.gesture() (proximity-scoped)"
```

---

## Task 5: `POST /api/parties/{slug}/gesture` route with cooldown

**Files:**
- Create: `backend/app/routes/expressive.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_gesture_route.py`
- Test: `backend/tests/test_gesture_cooldown.py`

- [ ] **Step 1: Write the failing route test**

Create `backend/tests/test_gesture_route.py`:

```python
from app.validation import ALLOWED_GESTURES
from tests.conftest import join_party, register_human


def test_gesture_emits_gesture_event(client):
    sess = register_human(client, username="Alice")
    join_party(client, sess, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    resp = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["gesture"] == "wave"
    assert "expires_at" in body
    assert "cursor" in body
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    gestures = [e for e in diff["events"] if e["type"] == "gesture"]
    assert len(gestures) == 1
    g = gestures[0]
    assert g["gesture"] == "wave"
    assert g["actor_username"] == "Alice"
    assert g["actor_kind"] == "human"
    assert g["room_wide"] is False
    assert g["expires_at"] > g["at"]


def test_gesture_bad_value_returns_422_with_allowed_list(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "twerk"},
    )
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"] == "invalid_gesture"
    assert body["allowed_gestures"] == list(ALLOWED_GESTURES)


def test_gesture_requires_party_membership(client):
    sess = register_human(client)
    # Not joined.
    resp = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "not_in_party"


def test_gesture_unknown_party_returns_404(client):
    sess = register_human(client)
    resp = client.post(
        "/api/parties/no-such-party/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Write the failing cooldown test**

Create `backend/tests/test_gesture_cooldown.py`:

```python
from tests.conftest import join_party, register_human


def test_gesture_burst_three_then_cooldown(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    # Burst of 3 succeeds.
    for _ in range(3):
        r = client.post(
            "/api/parties/cream-terrazzo/gesture",
            json={"principal": sess["principal"], "gesture": "wave"},
        )
        assert r.status_code == 200, r.json()
    # 4th immediately is rate-limited.
    r4 = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": sess["principal"], "gesture": "wave"},
    )
    assert r4.status_code == 429
    body = r4.json()["detail"]
    assert body["error"] == "rate_limited"
    assert body["scope"] == "gesture"
    assert isinstance(body["retry_after_ms"], int)
    assert body["retry_after_ms"] > 0


def test_gesture_bucket_does_not_share_with_chat(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    # Drain gesture bucket.
    for _ in range(3):
        client.post(
            "/api/parties/cream-terrazzo/gesture",
            json={"principal": sess["principal"], "gesture": "wave"},
        )
    # Chat still works (separate bucket).
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": sess["principal"], "text": "hello"},
    )
    assert r.status_code == 200, r.json()
```

- [ ] **Step 3: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_gesture_route.py tests/test_gesture_cooldown.py -v`
Expected: FAIL — endpoint does not exist (404).

- [ ] **Step 4: Create the expressive router**

Create `backend/app/routes/expressive.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import NOT_IN_PARTY, envelope
from app.rate_limit import RateLimitScope, TokenBucketRegistry
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import (
    ALLOWED_COSMETIC_EFFECTS,
    ALLOWED_GESTURES,
    CosmeticValidationError,
    GestureValidationError,
)
from app.world import ParticipantNotInPartyError, PartyWorld

router = APIRouter(prefix="/api/parties")

_SLUG_PATTERN = r"^[a-z0-9-]+$"


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


def _rate_limit_dep() -> TokenBucketRegistry:  # pragma: no cover - overridden
    raise NotImplementedError


def _world(store: Store, slug: str) -> PartyWorld:
    world = store.get_or_create_world(slug)
    if world is None:
        raise HTTPException(status_code=404, detail="party not found")
    return world


def _enforce_rate_limit(
    registry: TokenBucketRegistry, scope: RateLimitScope, actor_id: str
) -> None:
    res = registry.try_consume(scope.value, actor_id=actor_id)
    if not res.ok:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                "rate_limited",
                message=f"too many {scope.value} actions",
                scope=scope.value,
                retry_after_ms=res.retry_after_ms,
            ),
        )


class GestureRequest(BaseModel):
    principal: Principal
    gesture: str


@router.post("/{slug}/gesture")
def gesture(
    body: GestureRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
    rate_limit: TokenBucketRegistry = Depends(_rate_limit_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    _enforce_rate_limit(rate_limit, RateLimitScope.GESTURE, resolved.id)
    try:
        ev = world.gesture(resolved.id, body.gesture)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except GestureValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_gesture",
                message=str(exc),
                allowed_gestures=list(ALLOWED_GESTURES),
            ),
        )
    return {
        "gesture": ev.gesture,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
    }
```

Note: `NOT_IN_PARTY` from `app/errors.py` must already be the structured envelope `{"error": "not_in_party", "message": "..."}` per spec #01. If it is still a bare string, that's a spec #01 regression — file it, do not work around it here.

- [ ] **Step 5: Mount the router**

In `backend/app/main.py`, find the existing `app.include_router(reactions_router, ...)` block and add a matching include for `expressive`:

```python
from app.routes import expressive as expressive_routes
# ...
expressive_routes._store_dep = _provide_store  # or whatever the existing override pattern is
expressive_routes._rate_limit_dep = _provide_rate_limit  # provided by spec #03
app.include_router(expressive_routes.router)
```

Match the EXACT dependency-injection style already used for `reactions` in `main.py` — copy that block, don't invent a new one. If `_provide_rate_limit` does not exist, spec #03 has not finished wiring; STOP and report.

- [ ] **Step 6: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_gesture_route.py tests/test_gesture_cooldown.py -v`
Expected: PASS.

- [ ] **Step 7: Full backend suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routes/expressive.py backend/app/main.py \
        backend/tests/test_gesture_route.py backend/tests/test_gesture_cooldown.py
git commit -m "feat(api): POST /api/parties/{slug}/gesture with token-bucket cooldown"
```

---

## Task 6: Targeted reactions — extend `/react`

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/world.py`
- Modify: `backend/app/routes/reactions.py`
- Test: `backend/tests/test_react_targeted.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_react_targeted.py`:

```python
from tests.conftest import join_party, register_human


def test_react_with_target_actor_id_attaches_to_event(client):
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    bob_id = bob["principal"]["agent_id"] if "agent_id" in bob["principal"] else bob["principal"]["session_id"]
    # NOTE: the helper exposes the resolved id; if conftest provides a cleaner
    # accessor (e.g. sess["id"]), use that. Adapt to whichever field the
    # existing register_human returns.
    resolved_bob_id = bob["id"]
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "🔥",
            "target_actor_id": resolved_bob_id,
        },
    )
    assert resp.status_code == 200
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    rx = [e for e in diff["events"] if e["type"] == "reaction"][-1]
    assert rx["actor_username"] == "Alice"
    assert rx["target_actor_id"] == resolved_bob_id
    assert rx.get("target_seq") is None


def test_react_with_target_seq_attaches_to_event(client):
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")
    # Bob says hi — capture its seq.
    chat_resp = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": bob["principal"], "text": "hi all"},
    )
    bob_chat_seq = chat_resp.json()["seq"]
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "👍",
            "target_seq": bob_chat_seq,
        },
    )
    assert resp.status_code == 200
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    rx = [e for e in diff["events"] if e["type"] == "reaction"][-1]
    assert rx["target_seq"] == bob_chat_seq
    assert rx.get("target_actor_id") is None


def test_react_with_both_targets_is_422(client):
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "🔥",
            "target_seq": 1,
            "target_actor_id": bob["id"],
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_reaction_target"


def test_react_with_missing_target_actor_is_404(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "🔥",
            "target_actor_id": "no-such-participant",
        },
    )
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["error"] == "target_not_found"


def test_react_with_missing_target_seq_is_404(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={
            "principal": alice["principal"],
            "emoji": "🔥",
            "target_seq": 999_999,
        },
    )
    assert resp.status_code == 404
    body = resp.json()["detail"]
    assert body["error"] == "target_not_found"


def test_react_without_target_still_works(client):
    alice = register_human(client, username="Alice")
    join_party(client, alice, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": alice["principal"], "emoji": "🔥"},
    )
    assert resp.status_code == 200
```

If `register_human` / `join_party` do not expose the participant `id` as `sess["id"]`, look at `backend/tests/conftest.py` and use whichever accessor returns the resolved participant id (it may be `sess["principal"]["session_id"]` for humans or `sess["principal"]["agent_id"]` for agents — adapt the test to whichever conftest helper exposes).

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_react_targeted.py -v`
Expected: FAIL — request model has no `target_*` fields; `ReactionEvent` has no target fields.

- [ ] **Step 3: Extend `ReactionEvent` (additive optional fields)**

In `backend/app/events.py`, modify `ReactionEvent`:

```python
class ReactionEvent(BaseModel):
    seq: int
    type: Literal["reaction"] = "reaction"
    actor_id: str
    emoji: str
    expires_at: float
    at: float
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    target_seq: int | None = None
    target_actor_id: str | None = None
```

- [ ] **Step 4: Add a typed exception + extend `world.react`**

In `backend/app/world.py`:

```python
class ReactionTargetNotFoundError(LookupError):
    pass


class ReactionTargetConflictError(ValueError):
    pass
```

Place these near `ParticipantNotInPartyError`.

Modify `PartyWorld.react`:

```python
def react(
    self,
    participant_id: str,
    emoji: str,
    *,
    target_seq: int | None = None,
    target_actor_id: str | None = None,
) -> ReactionEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    if target_seq is not None and target_actor_id is not None:
        raise ReactionTargetConflictError("set at most one of target_seq/target_actor_id")
    if target_actor_id is not None and target_actor_id not in self.participants:
        raise ReactionTargetNotFoundError(target_actor_id)
    if target_seq is not None and (target_seq < 1 or target_seq > len(self._events)):
        raise ReactionTargetNotFoundError(str(target_seq))
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
        target_seq=target_seq,
        target_actor_id=target_actor_id,
        **self._actor_fields(participant_id),
    )
    self._events.append(ev)
    self._emit(ev)
    return ev
```

- [ ] **Step 5: Update the route**

In `backend/app/routes/reactions.py`:

```python
from app.world import (
    ParticipantNotInPartyError,
    PartyWorld,
    ReactionTargetConflictError,
    ReactionTargetNotFoundError,
)


class ReactRequest(BaseModel):
    principal: Principal
    emoji: str
    target_seq: int | None = None
    target_actor_id: str | None = None


@router.post("/{slug}/react")
def react(
    body: ReactRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.react(
            resolved.id,
            body.emoji,
            target_seq=body.target_seq,
            target_actor_id=body.target_actor_id,
        )
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except ReactionTargetConflictError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_reaction_target",
                message=str(exc),
            ),
        )
    except ReactionTargetNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=envelope(
                "target_not_found",
                message=f"target {exc!s} does not exist",
            ),
        )
    except ReactionValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_emoji",
                message=str(exc),
                allowed_emojis=list(REACTION_EMOJI_ALLOWLIST),
            ),
        )
    return {
        "emoji": ev.emoji,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
        "target_seq": ev.target_seq,
        "target_actor_id": ev.target_actor_id,
    }
```

- [ ] **Step 6: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_react_targeted.py -v`
Expected: PASS.

- [ ] **Step 7: Full backend suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS. Existing reaction tests are unchanged because target fields default to `None` and the response shape is additive.

- [ ] **Step 8: Commit**

```bash
git add backend/app/events.py backend/app/world.py \
        backend/app/routes/reactions.py backend/tests/test_react_targeted.py
git commit -m "feat(react): optional target_seq / target_actor_id on /react"
```

---

## Task 7: `CosmeticEvent` model + `world.cosmetic()` + `/cosmetic` route

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/world.py`
- Modify: `backend/app/routes/expressive.py`
- Test: `backend/tests/test_world_cosmetic.py`
- Test: `backend/tests/test_cosmetic_route.py`

- [ ] **Step 1: Write the failing world test**

Create `backend/tests/test_world_cosmetic.py`:

```python
import pytest

from app.events import CosmeticEvent, Participant
from app.models import PartyConfig, Room, WorldSize
from app.validation import COSMETIC_TTL_SECONDS, CosmeticValidationError
from app.world import ParticipantNotInPartyError, PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t", name="t",
        worldSize=WorldSize(width=800, height=600),
        room=Room(walls=[]),
        zones=[], modules=[],
    )
    return PartyWorld(party=party)


def _join(w: PartyWorld) -> Participant:
    p = Participant(
        id="p1", kind="agent", username="Maestro", color="#9c27b0",
        x=100.0, y=100.0, joined_at=0.0,
    )
    w.join(p)
    return p


def test_cosmetic_emits_event_with_actor_fields_and_room_wide_true():
    w = _world()
    _join(w)
    ev = w.cosmetic("p1", "confetti")
    assert isinstance(ev, CosmeticEvent)
    assert ev.effect == "confetti"
    assert ev.room_wide is True
    assert ev.actor_id == "p1"
    assert ev.actor_username == "Maestro"
    assert ev.actor_kind == "agent"
    assert ev.expires_at == pytest.approx(ev.at + COSMETIC_TTL_SECONDS, abs=0.05)


def test_cosmetic_unknown_raises():
    w = _world()
    _join(w)
    with pytest.raises(CosmeticValidationError):
        w.cosmetic("p1", "rain")


def test_cosmetic_unknown_participant_raises():
    w = _world()
    with pytest.raises(ParticipantNotInPartyError):
        w.cosmetic("ghost", "confetti")
```

- [ ] **Step 2: Write the failing route + cooldown test**

Create `backend/tests/test_cosmetic_route.py`:

```python
from app.validation import ALLOWED_COSMETIC_EFFECTS
from tests.conftest import join_party, register_human


def test_cosmetic_emits_event(client):
    sess = register_human(client, username="Alice")
    join_party(client, sess, "cream-terrazzo")
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    resp = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "confetti"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["effect"] == "confetti"
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cur}"
    ).json()
    cosm = [e for e in diff["events"] if e["type"] == "cosmetic"]
    assert len(cosm) == 1
    c = cosm[0]
    assert c["effect"] == "confetti"
    assert c["room_wide"] is True
    assert c["actor_username"] == "Alice"
    assert c["expires_at"] > c["at"]


def test_cosmetic_visible_to_distant_observer(client):
    """Cosmetic must reach observers regardless of proximity (room_wide)."""
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")
    # Move bob far away (assume worldSize big enough; values >> PROXIMITY_RADIUS).
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": bob["principal"], "x": 50.0, "y": 50.0},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": alice["principal"], "x": 950.0, "y": 650.0},
    )
    cur_bob = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"principal_id": bob["id"]},  # adapt to actual proximity param
    ).json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": alice["principal"], "effect": "sparkle"},
    )
    diff = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cur_bob, "principal_id": bob["id"]},
    ).json()
    cosm = [e for e in diff["events"] if e["type"] == "cosmetic"]
    assert len(cosm) == 1, "cosmetic must cross the room (room_wide=True)"


def test_cosmetic_bad_value_returns_422_with_allowed_list(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    resp = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "rain"},
    )
    assert resp.status_code == 422
    body = resp.json()["detail"]
    assert body["error"] == "invalid_cosmetic"
    assert body["allowed_effects"] == list(ALLOWED_COSMETIC_EFFECTS)


def test_cosmetic_cooldown_one_per_ten_seconds(client):
    sess = register_human(client)
    join_party(client, sess, "cream-terrazzo")
    r1 = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "confetti"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "confetti"},
    )
    assert r2.status_code == 429
    body = r2.json()["detail"]
    assert body["error"] == "rate_limited"
    assert body["scope"] == "cosmetic"
    assert 0 < body["retry_after_ms"] <= 10_000


def test_cosmetic_requires_party_membership(client):
    sess = register_human(client)
    resp = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": sess["principal"], "effect": "confetti"},
    )
    assert resp.status_code == 409
```

Note on the proximity test: pass whichever query parameter spec #02's scoped observer uses to identify the requesting participant. If spec #02 derives the requester from a header or principal body, adapt the call. The assertion that matters is "cosmetic events cross proximity boundaries"; the call shape is incidental.

- [ ] **Step 3: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_world_cosmetic.py tests/test_cosmetic_route.py -v`
Expected: FAIL — `CosmeticEvent` and `world.cosmetic` do not exist; route is 404.

- [ ] **Step 4: Add `CosmeticEvent` to `events.py`**

```python
class CosmeticEvent(BaseModel):
    seq: int
    type: Literal["cosmetic"] = "cosmetic"
    effect: str  # one of ALLOWED_COSMETIC_EFFECTS
    at: float
    expires_at: float
    room_wide: bool = True
    actor_id: str
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
```

Add `CosmeticEvent` to the `Event` union next to `GestureEvent`.

- [ ] **Step 5: Add `cosmetic()` to `PartyWorld`**

In `backend/app/world.py` (after `gesture`):

Add to the imports:
```python
from app.events import (
    # ...existing...
    CosmeticEvent,
    GestureEvent,
)
from app.validation import (
    # ...existing...
    COSMETIC_TTL_SECONDS,
    validate_cosmetic_effect,
)
```

Method:

```python
def cosmetic(self, participant_id: str, effect: str) -> CosmeticEvent:
    if participant_id not in self.participants:
        raise ParticipantNotInPartyError(participant_id)
    cleaned = validate_cosmetic_effect(effect)
    now = time.time()
    ev = CosmeticEvent(
        seq=self._next_seq(),
        effect=cleaned,
        at=now,
        expires_at=now + COSMETIC_TTL_SECONDS,
        room_wide=True,
        **self._actor_fields(participant_id),
    )
    self._events.append(ev)
    self._emit(ev)
    return ev
```

- [ ] **Step 6: Add the route**

Append to `backend/app/routes/expressive.py`:

```python
class CosmeticRequest(BaseModel):
    principal: Principal
    effect: str


@router.post("/{slug}/cosmetic")
def cosmetic(
    body: CosmeticRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
    rate_limit: TokenBucketRegistry = Depends(_rate_limit_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    _enforce_rate_limit(rate_limit, RateLimitScope.COSMETIC, resolved.id)
    try:
        ev = world.cosmetic(resolved.id, body.effect)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except CosmeticValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_cosmetic",
                message=str(exc),
                allowed_effects=list(ALLOWED_COSMETIC_EFFECTS),
            ),
        )
    return {
        "effect": ev.effect,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
    }
```

- [ ] **Step 7: Spec #02 observer must let `cosmetic` cross proximity**

Spec #02's scoped `/observe` filters events by proximity unless `room_wide=True`. Confirm that path treats `CosmeticEvent` correctly by reading the filter helper (likely `world.observe_since` or a `_visible_to` helper). The contract is "if `getattr(ev, 'room_wide', False) is True`, pass through unconditionally". If the existing filter hard-codes a list of event types, ADD `"cosmetic"` to the always-include list.

Codify with the `test_cosmetic_visible_to_distant_observer` test in step 2.

- [ ] **Step 8: Run, confirm pass**

Run: `cd backend && python -m pytest tests/test_world_cosmetic.py tests/test_cosmetic_route.py -v`
Expected: PASS.

- [ ] **Step 9: Full backend suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/events.py backend/app/world.py \
        backend/app/routes/expressive.py \
        backend/tests/test_world_cosmetic.py backend/tests/test_cosmetic_route.py
git commit -m "feat(api): POST /cosmetic — room-wide effect events with strict cooldown"
```

---

## Task 8: Avatar facing direction

**Files:**
- Modify: `backend/app/events.py`
- Modify: `backend/app/world.py`
- Test: `backend/tests/test_move_facing.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_move_facing.py`:

```python
import pytest

from app.events import Participant
from app.models import PartyConfig, Room, WorldSize
from app.world import PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t", name="t",
        worldSize=WorldSize(width=2000, height=2000),
        room=Room(walls=[]),
        zones=[], modules=[],
    )
    return PartyWorld(party=party)


def _join(w: PartyWorld) -> Participant:
    p = Participant(
        id="p1", kind="human", username="Alice", color="#ff6b9d",
        x=500.0, y=500.0, joined_at=0.0,
    )
    w.join(p)
    return p


@pytest.mark.parametrize("dx,dy,expected", [
    (0, -10, "up"),
    (0, 10, "down"),
    (-10, 0, "left"),
    (10, 0, "right"),
    (-10, -10, "up-left"),
    (10, -10, "up-right"),
    (-10, 10, "down-left"),
    (10, 10, "down-right"),
])
def test_move_derives_facing_for_each_octant(dx, dy, expected):
    w = _world()
    p = _join(w)
    ev = w.move("p1", p.x + dx, p.y + dy)
    assert ev.facing == expected
    assert w.participants["p1"].facing == expected


def test_move_zero_delta_retains_previous_facing():
    w = _world()
    p = _join(w)
    # Initial move sets facing to "right".
    w.move("p1", p.x + 10, p.y)
    assert w.participants["p1"].facing == "right"
    # Same-position move retains.
    ev = w.move("p1", p.x + 10, p.y)
    assert ev.facing == "right"
    assert w.participants["p1"].facing == "right"


def test_initial_participant_facing_defaults_to_down():
    w = _world()
    p = _join(w)
    # Before any move, facing should be the default the spec picks.
    assert p.facing == "down"
    assert w.participants["p1"].facing == "down"


def test_observe_participant_includes_facing():
    w = _world()
    _join(w)
    w.move("p1", 510.0, 510.0)
    snap = w.snapshot()
    me = next(p for p in snap["participants"] if p["id"] == "p1")
    assert me["facing"] == "down-right"
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_move_facing.py -v`
Expected: FAIL — `Participant` has no `facing` field; `MoveEvent` has no `facing` field.

- [ ] **Step 3: Extend `Participant` and `MoveEvent`**

In `backend/app/events.py`:

```python
Facing = Literal[
    "up", "down", "left", "right",
    "up-left", "up-right", "down-left", "down-right",
]


class Participant(BaseModel):
    id: str
    kind: Literal["human", "agent"]
    username: str
    color: str
    x: float
    y: float
    joined_at: float
    facing: Facing = "down"
```

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
    facing: Facing | None = None
```

- [ ] **Step 4: Compute facing inside `world.move`**

In `backend/app/world.py`, add a helper near `_actor_fields`:

```python
def _derive_facing(self, dx: float, dy: float, fallback: str) -> str:
    # Use a small dead-zone to ignore sub-pixel jitter from the slide solver.
    epsilon = 0.5
    horiz = 0
    vert = 0
    if dx > epsilon:
        horiz = 1
    elif dx < -epsilon:
        horiz = -1
    if dy > epsilon:
        vert = 1
    elif dy < -epsilon:
        vert = -1
    if horiz == 0 and vert == 0:
        return fallback
    pieces: list[str] = []
    if vert == -1:
        pieces.append("up")
    elif vert == 1:
        pieces.append("down")
    if horiz == -1:
        pieces.append("left")
    elif horiz == 1:
        pieces.append("right")
    return "-".join(pieces)
```

Modify `PartyWorld.move`:

```python
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
    new_facing = self._derive_facing(
        new_x - current.x, new_y - current.y, fallback=current.facing
    )
    self.participants[participant_id] = current.model_copy(
        update={"x": new_x, "y": new_y, "facing": new_facing}
    )
    ev = MoveEvent(
        seq=self._next_seq(),
        participant_id=participant_id,
        x=new_x,
        y=new_y,
        at=time.time(),
        facing=new_facing,
        **self._actor_fields(participant_id),
    )
    self._events.append(ev)
    self._emit(ev)
    self._recompute_all_drawboard_votes(time.time())
    return ev
```

- [ ] **Step 5: Expose `facing` in the participant projection used by `/observe`**

In `backend/app/world.py`, update `_participant_dict`:

```python
def _participant_dict(self, p: Participant) -> dict:
    return {
        "id": p.id,
        "kind": p.kind,
        "username": p.username,
        "color": p.color,
        "x": p.x,
        "y": p.y,
        "facing": p.facing,
        "zone": self.derive_zone(p.x, p.y),
    }
```

- [ ] **Step 6: Run, confirm pass**

Run: `cd backend && python -m pytest tests/test_move_facing.py -v`
Expected: PASS.

- [ ] **Step 7: Full backend suite**

Run: `cd backend && python -m pytest -x --tb=short`
Expected: ALL PASS. If existing observe tests assert exact participant-dict equality, they need `facing` added — update those assertions to use subset comparison or include the new key.

- [ ] **Step 8: Commit**

```bash
git add backend/app/events.py backend/app/world.py backend/tests/test_move_facing.py
git commit -m "feat(world): derive avatar facing from move delta (8 dirs + retention)"
```

---

## Task 9: Frontend types + agent guide

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `backend/app/routes/agent_guide.py`
- Test: `backend/tests/test_agent_guide_expressive.py` (new)

- [ ] **Step 1: Write the failing guide test**

Create `backend/tests/test_agent_guide_expressive.py`:

```python
def test_guide_documents_gestures(client):
    body = client.get("/api/agent-guide").text
    for g in ("wave", "point", "dance", "jump", "sit", "shiver", "bow", "nod"):
        assert g in body
    assert "/gesture" in body


def test_guide_documents_gesture_cooldown(client):
    body = client.get("/api/agent-guide").text
    # Mentions the burst and refill so an agent can pace itself.
    assert "burst" in body.lower()
    assert "2 second" in body or "2s" in body


def test_guide_documents_cosmetics(client):
    body = client.get("/api/agent-guide").text
    for e in ("confetti", "sparkle", "lights_flash", "ping"):
        assert e in body
    assert "/cosmetic" in body
    assert "room" in body.lower()  # mentions it's room-wide
    assert "10 second" in body or "10s" in body  # cooldown


def test_guide_documents_targeted_reactions(client):
    body = client.get("/api/agent-guide").text
    assert "target_seq" in body
    assert "target_actor_id" in body


def test_guide_documents_facing(client):
    body = client.get("/api/agent-guide").text
    assert "facing" in body
    for d in ("up", "down", "left", "right"):
        assert d in body
```

- [ ] **Step 2: Run, confirm failure**

Run: `cd backend && python -m pytest tests/test_agent_guide_expressive.py -v`
Expected: FAIL.

- [ ] **Step 3: Extend the agent guide**

In `backend/app/routes/agent_guide.py`, add imports:

```python
from app.validation import ALLOWED_COSMETIC_EFFECTS, ALLOWED_GESTURES

_GESTURE_LIST = ", ".join(f"`{g}`" for g in ALLOWED_GESTURES)
_COSMETIC_LIST = ", ".join(f"`{e}`" for e in ALLOWED_COSMETIC_EFFECTS)
```

Append a new section to the `_GUIDE` body (placed after the existing reactions section):

```markdown
## Gestures

`POST /api/parties/{slug}/gesture` body `{principal, gesture}` →
`{"gesture", "expires_at", "cursor"}`.

Allowed `gesture`: {_GESTURE_LIST}.

Emits a `gesture` event with `actor_id`, `actor_username`, `actor_kind`,
`seq`, `at`, `expires_at` (default 2 seconds after `at`), and
`room_wide: false`. Gestures are proximity-scoped — only nearby
participants see them.

Cooldown: token bucket, burst of 3, refill 1 per 2 seconds. Exceeding it
returns 422 → 429 with `{detail: {error: "rate_limited", scope: "gesture",
retry_after_ms}}`.

Use gestures for *intent* (waving hi, pointing at a board, dancing along
to chat) — they don't pollute the chat channel and are cheaper than chats
to send back-to-back.

## Targeted reactions

`POST .../react` accepts optional `target_seq` (the seq of the event being
reacted to) OR `target_actor_id` (the participant being reacted at). At
most one may be set. If the target doesn't exist you get a 404 with
`{error: "target_not_found"}`. The resulting `reaction` event echoes the
target field so the UI can attach the floater to the target instead of
the reactor.

## Cosmetic room effects

`POST /api/parties/{slug}/cosmetic` body `{principal, effect}` →
`{"effect", "expires_at", "cursor"}`.

Allowed `effect`: {_COSMETIC_LIST}.

Emits a `cosmetic` event with `room_wide: true` — everyone in the room
sees it, regardless of distance. Default TTL is 3 seconds.

Cooldown is strict: burst of 1, refill 1 per 10 seconds. Use these for
"loud but not chat" moments — confetti on a milestone, a sparkle on
agreement, a ping to get attention.

## Avatar facing direction

Every `Participant` carries a `facing` field — one of `up`, `down`,
`left`, `right`, `up-left`, `up-right`, `down-left`, `down-right`. The
server derives it from the (dx, dy) of each `/move`. If `dx == dy == 0`
the previous facing is retained. The `move` event payload also includes
`facing` so observers can update their render without re-snapshotting.

Use this for mirror / follow personas: read the target's `facing` from
`/observe` and match it to look "with" them.
```

The triple-backtick markdown fences inside the Python `_GUIDE` string are escaped per existing file conventions — match the style already used for the rest of the guide.

- [ ] **Step 4: Re-run, confirm pass**

Run: `cd backend && python -m pytest tests/test_agent_guide_expressive.py -v`
Expected: PASS.

- [ ] **Step 5: Update frontend types**

In `frontend/src/api/types.ts`, add:

```ts
export type Facing =
  | "up" | "down" | "left" | "right"
  | "up-left" | "up-right" | "down-left" | "down-right";

export interface GestureEvent {
  type: "gesture";
  seq: number;
  gesture:
    | "wave" | "point" | "dance" | "jump"
    | "sit" | "shiver" | "bow" | "nod";
  at: number;
  expires_at: number;
  room_wide: false;
  actor_id: string;
  actor_username?: string;
  actor_kind?: "human" | "agent";
}

export interface CosmeticEvent {
  type: "cosmetic";
  seq: number;
  effect: "confetti" | "sparkle" | "lights_flash" | "ping";
  at: number;
  expires_at: number;
  room_wide: true;
  actor_id: string;
  actor_username?: string;
  actor_kind?: "human" | "agent";
}
```

Extend `ReactionEvent` (existing interface — find it, add optional fields):

```ts
target_seq?: number;
target_actor_id?: string;
```

Extend `MoveEvent`:
```ts
facing?: Facing;
```

Extend `Participant`:
```ts
facing?: Facing;
```

Add `GestureEvent | CosmeticEvent` to the `RealtimeEvent` union (or whatever the discriminated-union name is — match the existing pattern).

- [ ] **Step 6: Frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS. No existing consumer reads the new types yet, so this is purely additive.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_expressive.py \
        frontend/src/api/types.ts
git commit -m "docs(guide,types): document gestures, cosmetics, targeted reactions, facing"
```

---

## Task 10: Final verification + CLAUDE.md note

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Full backend suite**

Run: `cd backend && python -m pytest --tb=short`
Expected: ALL PASS.

- [ ] **Step 2: Full frontend suite**

Run: `cd frontend && npm test -- --run`
Expected: ALL PASS.

- [ ] **Step 3: Manual smoke-test against a live server**

Run: `cd backend && python -m uvicorn app.main:app --port 8901 &`

```bash
# Register + join (use the helper endpoints — adapt to whatever main.py exposes)
curl -s -X POST http://localhost:8901/api/sessions -H 'content-type: application/json' \
     -d '{"username":"Smoke"}' > /tmp/s.json
SID=$(python -c "import json;print(json.load(open('/tmp/s.json'))['session_id'])")
curl -s -X POST http://localhost:8901/api/parties/cream-terrazzo/join \
     -H 'content-type: application/json' \
     -d "{\"principal\":{\"session_id\":\"$SID\"}}"

# Gesture
curl -s -X POST http://localhost:8901/api/parties/cream-terrazzo/gesture \
     -H 'content-type: application/json' \
     -d "{\"principal\":{\"session_id\":\"$SID\"},\"gesture\":\"wave\"}"

# Cosmetic
curl -s -X POST http://localhost:8901/api/parties/cream-terrazzo/cosmetic \
     -H 'content-type: application/json' \
     -d "{\"principal\":{\"session_id\":\"$SID\"},\"effect\":\"confetti\"}"

# Observe and confirm both events appeared
curl -s http://localhost:8901/api/parties/cream-terrazzo/observe | python -m json.tool | head -80
```

Kill the server: `kill %1`.

- [ ] **Step 4: Update CLAUDE.md**

Append (or place in the appropriate "What's Implemented" section):

```
- Expressive actions (2026-05-26): /gesture (wave/point/dance/jump/sit/shiver/bow/nod, burst 3, 1/2s),
  /cosmetic (confetti/sparkle/lights_flash/ping, room-wide, 1/10s), targeted reactions
  (target_seq | target_actor_id), avatar facing direction (8-way, derived from move).
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): note expressive-actions feature landed"
```

- [ ] **Step 6: Summary review**

Run: `git log --oneline main..HEAD`
Expected: a clean linear series of small commits — one per task.

---

## Self-review checklist

1. **Spec coverage** — every numbered point in feature-backlog §2 maps to a task in the Spec → Task Map at the top.
2. **No placeholders** — every code block contains actual code; no TODOs.
3. **Type / name consistency** — `gesture`, `cosmetic`, `effect`, `target_seq`, `target_actor_id`, `facing` use the same names in events.py, world.py, routes, the guide, and types.ts.
4. **Backwards compatibility** — `target_seq`/`target_actor_id` on `/react` default to `None`; `facing` defaults to `"down"` on existing `Participant`; new event types are additive in the `Event` union; route additions don't change existing endpoints.
5. **Cooldown isolation** — chat, gesture, and cosmetic each have their own scope key. Gesture-bucket exhaustion does not block chat (asserted in `test_gesture_bucket_does_not_share_with_chat`).
6. **Room-wide flag** — `gesture` always `False`, `cosmetic` always `True`, asserted in both world tests and route tests. Spec #02's observer filter must let `room_wide=True` cross proximity unconditionally.

---

## Out of scope (do not creep)

- Visual rendering of gestures / cosmetics in the frontend canvas — types ship; the component work belongs to a future UI plan.
- Server-side animation timing / interpolation. The TTL on the event is the contract; rendering is purely client-side.
- Persisting gestures or cosmetics across server restart — they're ephemeral by design.
- Chat enhancements (mentions, reply_to, room-wide chat scope) — spec #03.
- Follow / proposal / `actor_color` propagation — spec #06.
- Frontend animation library choice — out of scope; types only.
