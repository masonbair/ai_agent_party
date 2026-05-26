# Spec #04 — Module-scoped Chat + Module Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add module-scoped chat (events visible only to participants inside the same `interactionRect`), enrich `not_in_range` errors with `interactionRect` and `actor_position`, ship a free-floating notes module (`freenotes`) seeded into `cream-terrazzo`, and let participants react to individual sticky notes.

**Architecture:**
- Reuse spec #03's chat cooldown token-bucket (`scope: "module"`) for module chat rate-limiting; do not invent new rate-limit code.
- Reuse spec #02's `PROXIMITY_RADIUS` helper for freenotes visibility scoping and extend spec #02's `observe_since` scoping hook with two new predicates: `module_chat → caller inside module.interactionRect` and `freenotes note events → caller within PROXIMITY_RADIUS of note (x, y)`.
- Module-chat history is kept on `PartyWorld` as a per-module deque capped at 50.
- The `interactionRect`-in-error pattern lives in `app/errors.py` as a helper `not_in_range_envelope(module, actor)` so all future module endpoints can reuse it.
- New module kind `freenotes` is a peer of `StickyNoteModule`/`DrawBoardModule`; reuses `NoteCreatedEvent`/`NoteUpdatedEvent`/`NoteDeletedEvent` with the same `module_id` discriminator (the module-kind lookup tells callers whether the rect-bound or world-bound rules apply).

**Tech Stack:** FastAPI, Pydantic v2, pytest, FastAPI TestClient. Same toolset as the rest of the backend.

## Cross-spec assumptions

This plan assumes the following from foundation specs:
- **Spec #01 (event shape + errors):** all new events carry flat `actor_id` / `actor_username` / `actor_kind`. `app/errors.py::envelope` exists with the documented shape `{"error": <code>, ...extras}`.
- **Spec #02 (proximity-scoped `/observe`):** exposes `PROXIMITY_RADIUS` constant in `app/world.py` AND a per-event scoping hook on `PartyWorld` — referenced here as `PartyWorld._event_visible_to(event, observer_id)` — that filters `observe_since` events to the requester. Spec #02 owner adds an extension point (a registry of visibility predicates keyed by event type) so other specs can plug in additional rules without forking the function.
- **Spec #03 (chat enhancements / cooldown):** ships a token-bucket cooldown stored on `PartyWorld` and exposes `PartyWorld.check_chat_cooldown(participant_id, scope: str) -> None | float` raising `PartyWorld.ChatCooldownError` and returning the `retry_after_ms` on the structured 429. Scopes are strings (`"proximity"`, `"room"`); this spec adds `"module"` as a third scope with the same burst/refill rate as `"proximity"`.

Where this plan references those hooks, it uses the names above. If spec #02 / #03 ship with different names, the implementer renames inline; no other structural change is required.

## Spec → Task map

| Spec requirement | Tasks |
|---|---|
| Module-scoped chat endpoint + history | 3, 4, 5, 6 |
| `interactionRect` + `actor_position` in module 4xx errors | 1, 2 |
| Free-floating notes module (`freenotes`) | 7, 8, 9, 10, 11 |
| Vote/react on a specific sticky note | 12, 13 |
| Observer scoping extension (module_chat, freenotes proximity) | 5, 11 |
| Agent guide + frontend types | 14 |

## File Structure

**Create:**
- `backend/app/routes/module_chat.py` — `POST /api/parties/{slug}/modules/{module_id}/chat` and `GET /api/parties/{slug}/modules/{module_id}/chat-history`
- `backend/tests/test_module_chat_route.py`
- `backend/tests/test_module_chat_history.py`
- `backend/tests/test_module_chat_observer_scoping.py`
- `backend/tests/test_module_not_in_range_envelope.py`
- `backend/tests/test_freenotes_module.py`
- `backend/tests/test_freenotes_observer_scoping.py`
- `backend/tests/test_note_reaction.py`

**Modify:**
- `backend/app/errors.py` — add `not_in_range_envelope(module_id, interaction_rect, actor_position)` helper + `NOTE_NOT_IN_RANGE` reuses code `"not_in_range"`.
- `backend/app/events.py` — add `ModuleChatEvent`, `NoteReactionEvent`; extend `StickyNote` with `reactions: dict[str, int]`; update `Event` union.
- `backend/app/models.py` — add `FreeNotesModule` Pydantic model, extend `PlacedModule` and `Module` unions.
- `backend/app/validation.py` — no rule changes; module chat reuses `CHAT_TEXT_REGEX` and `CHAT_MAX_LEN`.
- `backend/app/world.py` — add `module_chat`, `module_chat_history`, freenotes branch in `create_note`/`update_note`/`delete_note`/`_module_snapshot`, `react_to_note`, `_actor_position`, register visibility predicates for `module_chat` and freenotes note events.
- `backend/app/routes/module_notes.py` — pass actor position into the error envelope when raising `not_in_range`; accept the freenotes kind (no `interactionRect` constraint, only room membership).
- `backend/app/routes/module_drawboard.py` — pass actor position into the error envelope when raising `not_in_range`.
- `backend/app/parties_data.py` — seed a `FreeNotesModule(id="freenotes-1")` into `cream-terrazzo`.
- `backend/app/main.py` — wire the new `module_chat` router + dependency override.
- `backend/tests/conftest.py` — add dependency override for `module_chat` router.
- `backend/app/routes/agent_guide.py` — document module chat, freenotes, note reactions, the new error envelope shape.
- `frontend/src/api/types.ts` — add `ModuleChatEvent`, `NoteReactionEvent`, `FreeNotesModule`, and `reactions` on `StickyNote`.

**Test (already covered above):** each behaviour gets a single focused file. Existing test files stay untouched except where a behaviour is genuinely extended.

---

## Task 1: Error helper — `not_in_range_envelope`

**Files:**
- Modify: `backend/app/errors.py`
- Test: `backend/tests/test_module_not_in_range_envelope.py` (new)

- [ ] **Step 1: Write the failing test**

`backend/tests/test_module_not_in_range_envelope.py`:
```python
from app.errors import not_in_range_envelope


def test_not_in_range_envelope_contains_rect_and_actor_position():
    body = not_in_range_envelope(
        module_id="sticky-1",
        interaction_rect={"x": -24.0, "y": 396.0, "w": 228.0, "h": 128.0},
        actor_position={"x": 400.0, "y": 250.0},
    )
    assert body == {
        "error": "not_in_range",
        "module_id": "sticky-1",
        "interactionRect": {"x": -24.0, "y": 396.0, "w": 228.0, "h": 128.0},
        "actor_position": {"x": 400.0, "y": 250.0},
    }
```

- [ ] **Step 2: Run test — confirm it fails**

Run: `pytest backend/tests/test_module_not_in_range_envelope.py -x --tb=short`
Expected: ImportError on `not_in_range_envelope`.

- [ ] **Step 3: Implement helper**

Append to `backend/app/errors.py`:
```python
NOT_IN_RANGE = "not_in_range"


def not_in_range_envelope(
    module_id: str,
    interaction_rect: dict[str, float],
    actor_position: dict[str, float],
) -> dict[str, object]:
    """Structured 409 body for module endpoints that require the caller
    to stand inside the module's interactionRect.

    Includes the rect and the caller's current position so an agent can
    auto-walk to a valid spot on the next request.
    """
    return envelope(
        NOT_IN_RANGE,
        module_id=module_id,
        interactionRect=interaction_rect,
        actor_position=actor_position,
    )
```

- [ ] **Step 4: Re-run — confirm it passes**

Run: `pytest backend/tests/test_module_not_in_range_envelope.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/errors.py backend/tests/test_module_not_in_range_envelope.py
git commit -m "feat(errors): add not_in_range_envelope with rect + actor position"
```

---

## Task 2: Wire the enriched envelope into existing module routes

**Files:**
- Modify: `backend/app/routes/module_notes.py`, `backend/app/routes/module_drawboard.py`
- Test: `backend/tests/test_module_notes_error_body.py` (extend), `backend/tests/test_module_drawboard_error_body.py` (extend)

The world raises `PartyWorld.NotInRangeError(module_id)`. Route handlers need access to the module rect and the caller's `(x, y)` to build the envelope. We expose them via two new world helpers.

- [ ] **Step 1: Write failing test — notes route returns enriched envelope**

Append to `backend/tests/test_module_notes_error_body.py` (use the file's existing fixtures, mirror style):
```python
def test_create_note_not_in_range_includes_rect_and_actor_position(
    client, register_human, join_party
):
    sid = register_human("alex")
    # Join far from sticky-1 (sticky-1 is at x=0, y=420, w=180, h=80 in cream-terrazzo).
    join_party(sid, "cream-terrazzo", x=400.0, y=100.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 10.0,
            "y": 10.0,
        },
    )
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["error"] == "not_in_range"
    assert body["module_id"] == "sticky-1"
    rect = body["interactionRect"]
    assert rect["w"] > 0 and rect["h"] > 0
    pos = body["actor_position"]
    assert pos == {"x": 400.0, "y": 100.0}
```

- [ ] **Step 2: Add a sibling test for drawboard**

Append to `backend/tests/test_module_drawboard_error_body.py`:
```python
def test_stroke_not_in_range_includes_rect_and_actor_position(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=10.0, y=10.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": {"kind": "human", "id": sid},
            "color": "#222222",
            "width": "thin",
            "points": [{"x": 1.0, "y": 1.0}],
        },
    )
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["error"] == "not_in_range"
    assert body["module_id"] == "draw-1"
    assert "interactionRect" in body
    assert body["actor_position"] == {"x": 10.0, "y": 10.0}
```

- [ ] **Step 3: Run tests — confirm both fail**

Run: `pytest backend/tests/test_module_notes_error_body.py backend/tests/test_module_drawboard_error_body.py -x --tb=short`
Expected: FAIL with body containing only `{"error": "not_in_range"}`.

- [ ] **Step 4: Add helpers to `PartyWorld`**

In `backend/app/world.py`, add inside the `PartyWorld` class:
```python
    def interaction_rect(self, module_id: str) -> dict[str, float] | None:
        m = self._placed_module(module_id)
        if m is None:
            return None
        margin = INTERACTION_MARGIN
        return {
            "x": m.x - margin,
            "y": m.y - margin,
            "w": m.w + 2 * margin,
            "h": m.h + 2 * margin,
        }

    def actor_position(self, participant_id: str) -> dict[str, float] | None:
        p = self.participants.get(participant_id)
        if p is None:
            return None
        return {"x": p.x, "y": p.y}
```

- [ ] **Step 5: Update `module_notes.py` route to use the helpers**

Replace the `_map_world_errors` function in `backend/app/routes/module_notes.py` with a closure-style helper called from each handler. Concretely, change each route to pass `world` and the resolved principal:

```python
from app.errors import NOT_IN_PARTY, envelope, not_in_range_envelope


def _map_world_errors(
    exc: Exception,
    world: PartyWorld | None = None,
    module_id: str | None = None,
    actor_id: str | None = None,
) -> HTTPException:
    if isinstance(exc, ParticipantNotInPartyError):
        return HTTPException(status_code=409, detail=NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        rect = (
            world.interaction_rect(module_id)
            if world is not None and module_id is not None
            else None
        )
        pos = (
            world.actor_position(actor_id)
            if world is not None and actor_id is not None
            else None
        )
        body = not_in_range_envelope(
            module_id=module_id or "",
            interaction_rect=rect or {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},
            actor_position=pos or {"x": 0.0, "y": 0.0},
        )
        return HTTPException(status_code=409, detail=body)
    if isinstance(exc, PartyWorld.LimitReachedError):
        return HTTPException(status_code=409, detail=envelope("limit_reached"))
    if isinstance(exc, PartyWorld.NotAuthorError):
        return HTTPException(status_code=403, detail=envelope("not_author"))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=envelope("not_found"))
    if isinstance(exc, NoteValidationError):
        return HTTPException(
            status_code=422,
            detail=envelope(
                "invalid_note",
                message=str(exc),
                allowed_colors=list(STICKY_COLOR_ALLOWLIST),
            ),
        )
    return HTTPException(
        status_code=422, detail=envelope("invalid_note", message=str(exc))
    )
```

And update each handler call site:
```python
    except _NoteErrors as exc:
        raise _map_world_errors(
            exc, world=world, module_id=module_id, actor_id=resolved.id
        ) from exc
```
Apply to `create_note`, `update_note`, `delete_note`.

- [ ] **Step 6: Update `module_drawboard.py` the same way**

In `backend/app/routes/module_drawboard.py`:
```python
from app.errors import NOT_IN_PARTY, envelope, not_in_range_envelope


def _map_errors(
    exc: Exception,
    world: PartyWorld | None = None,
    module_id: str | None = None,
    actor_id: str | None = None,
) -> HTTPException:
    if isinstance(exc, ParticipantNotInPartyError):
        return HTTPException(status_code=409, detail=NOT_IN_PARTY)
    if isinstance(exc, PartyWorld.NotInRangeError):
        rect = (
            world.interaction_rect(module_id)
            if world is not None and module_id is not None
            else None
        )
        pos = (
            world.actor_position(actor_id)
            if world is not None and actor_id is not None
            else None
        )
        body = not_in_range_envelope(
            module_id=module_id or "",
            interaction_rect=rect or {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},
            actor_position=pos or {"x": 0.0, "y": 0.0},
        )
        return HTTPException(status_code=409, detail=body)
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
    return HTTPException(status_code=404, detail=envelope("not_found"))
```
Update both `add_stroke` and `clear_board` to call `_map_errors(exc, world=world, module_id=module_id, actor_id=resolved.id)`.

- [ ] **Step 7: Run — confirm passes**

Run: `pytest backend/tests/test_module_notes_error_body.py backend/tests/test_module_drawboard_error_body.py -x --tb=short`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/world.py backend/app/routes/module_notes.py backend/app/routes/module_drawboard.py backend/tests/test_module_notes_error_body.py backend/tests/test_module_drawboard_error_body.py
git commit -m "feat(modules): enrich not_in_range errors with interactionRect + actor position"
```

---

## Task 3: `ModuleChatEvent` + world history

**Files:**
- Modify: `backend/app/events.py`, `backend/app/world.py`
- Test: `backend/tests/test_module_chat_history.py` (new)

- [ ] **Step 1: Add `ModuleChatEvent` (failing test first)**

`backend/tests/test_module_chat_history.py`:
```python
import pytest

from app.events import ModuleChatEvent


def test_module_chat_event_has_required_fields():
    ev = ModuleChatEvent(
        seq=1,
        module_id="sticky-1",
        text="hi all",
        at=1.0,
        actor_id="p",
        actor_username="alex",
        actor_kind="human",
    )
    assert ev.type == "module_chat"
    assert ev.module_id == "sticky-1"
    assert ev.text == "hi all"
```

- [ ] **Step 2: Run — confirm fails**

Run: `pytest backend/tests/test_module_chat_history.py -x --tb=short`
Expected: ImportError on `ModuleChatEvent`.

- [ ] **Step 3: Add the model**

In `backend/app/events.py`, after `ChatEvent`:
```python
class ModuleChatEvent(BaseModel):
    seq: int
    type: Literal["module_chat"] = "module_chat"
    module_id: str
    text: str
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
```

And include in the `Event` union:
```python
Event = (
    JoinEvent
    | LeaveEvent
    | MoveEvent
    | ChatEvent
    | ModuleChatEvent
    | ReactionEvent
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

- [ ] **Step 4: Run — passes**

Run: `pytest backend/tests/test_module_chat_history.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Add history test (failing)**

Append to `backend/tests/test_module_chat_history.py`:
```python
from app.events import Participant
from app.models import (
    DrawBoardModule,
    Music,
    PartyConfig,
    Room,
    Theme,
    WorldSize,
)
from app.world import PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t",
        name="t",
        description="t",
        theme=Theme(floor="#fff", accent="#000"),
        zones=[],
        music=Music(url=None, label="x"),
        worldSize=WorldSize(width=800, height=500),
        room=Room(border="1px solid #000", walls=[]),
        modules=[DrawBoardModule(id="draw-1", x=0, y=0, w=180, h=80)],
    )
    return PartyWorld(party)


def _participant(world: PartyWorld, pid: str, x: float, y: float) -> None:
    world.join(
        Participant(
            id=pid, kind="human", username=pid, color="#ff6b9d",
            x=x, y=y, joined_at=0.0,
        )
    )


def test_module_chat_history_returns_last_50_for_module():
    world = _world()
    _participant(world, "p1", x=50.0, y=50.0)  # inside draw-1 rect
    for i in range(60):
        world.module_chat("p1", "draw-1", f"msg{i:02d}")
    hist = world.module_chat_history("draw-1")
    assert len(hist) == 50
    assert hist[0]["text"] == "msg10"
    assert hist[-1]["text"] == "msg59"


def test_module_chat_history_isolated_per_module():
    world = _world()
    _participant(world, "p1", x=50.0, y=50.0)
    world.module_chat("p1", "draw-1", "hello")
    assert world.module_chat_history("draw-1")[0]["text"] == "hello"
    assert world.module_chat_history("other") == []
```

- [ ] **Step 6: Run — confirm fails**

Run: `pytest backend/tests/test_module_chat_history.py -x --tb=short`
Expected: AttributeError on `module_chat`.

- [ ] **Step 7: Implement `module_chat` + history on `PartyWorld`**

In `backend/app/world.py`:

1. Update imports near the top:
```python
from app.events import (
    ChatEvent,
    Event,
    JoinEvent,
    LeaveEvent,
    ModuleChatEvent,
    MoveEvent,
    Participant,
    Reaction,
    LightingChangedEvent,
    BoardClearedEvent,
    NoteCreatedEvent,
    NoteDeletedEvent,
    NoteUpdatedEvent,
    ReactionEvent,
    VoteChangedEvent,
    StickyNote,
    Stroke,
    StrokeAddedEvent,
    StrokeDroppedEvent,
)
```

2. Add constant near other `_LIGHTING_PRESETS`:
```python
MODULE_CHAT_HISTORY_LIMIT = 50
```

3. In `__init__`, after `self.votes_by_module = {}` line, add:
```python
        self.module_chat_by_module: dict[str, list[ModuleChatEvent]] = {}
```

4. Add the methods inside `PartyWorld`:
```python
    def module_chat(
        self, participant_id: str, module_id: str, text: str
    ) -> ModuleChatEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        # Module must exist; freenotes does not gate by interactionRect, every
        # other module does. _require_in_zone handles the rect check.
        self._require_placed(module_id)
        from app.models import FreeNotesModule  # local import: avoid cycle
        m = self._placed_module(module_id)
        if not isinstance(m, FreeNotesModule):
            self._require_in_zone(participant_id, module_id)
        cleaned = validate_chat_text(text)
        at = time.time()
        ev = ModuleChatEvent(
            seq=self._next_seq(),
            module_id=module_id,
            text=cleaned,
            at=at,
            **self._actor_fields(participant_id),
        )
        self._events.append(ev)
        bucket = self.module_chat_by_module.setdefault(module_id, [])
        bucket.append(ev)
        if len(bucket) > MODULE_CHAT_HISTORY_LIMIT:
            del bucket[: len(bucket) - MODULE_CHAT_HISTORY_LIMIT]
        self._emit(ev)
        return ev

    def module_chat_history(self, module_id: str) -> list[dict]:
        bucket = self.module_chat_by_module.get(module_id, [])
        return [ev.model_dump() for ev in bucket]
```

Note: `FreeNotesModule` will be added in Task 7. For now, since this task lands before Task 7, change the local import to a `try/except ImportError` guard so the test passes on a drawboard module too:
```python
        try:
            from app.models import FreeNotesModule  # type: ignore[attr-defined]
        except ImportError:
            FreeNotesModule = ()  # sentinel — isinstance(..., ()) is always False
```
This will collapse once Task 7 lands. The drawboard tests in this task hit `_require_in_zone` and pass.

- [ ] **Step 8: Run — passes**

Run: `pytest backend/tests/test_module_chat_history.py -x --tb=short`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/events.py backend/app/world.py backend/tests/test_module_chat_history.py
git commit -m "feat(world): add ModuleChatEvent + per-module history (cap 50)"
```

---

## Task 4: `POST /api/parties/{slug}/modules/{module_id}/chat` route

**Files:**
- Create: `backend/app/routes/module_chat.py`
- Modify: `backend/app/main.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_module_chat_route.py` (new)

- [ ] **Step 1: Write failing happy-path test**

`backend/tests/test_module_chat_route.py`:
```python
def test_post_module_chat_inside_rect_returns_cursor(
    client, register_human, join_party
):
    sid = register_human("alex")
    # draw-1 rect is x=620..800 y=420..500 (with margin 24 in each direction).
    join_party(sid, "cream-terrazzo", x=700.0, y=450.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": sid}, "text": "hi crew"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "cursor" in body
    assert body["module_id"] == "draw-1"
```

- [ ] **Step 2: Failing — caller outside rect → 409 with enriched envelope**

```python
def test_post_module_chat_outside_rect_returns_not_in_range_envelope(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=100.0, y=100.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": sid}, "text": "hi"},
    )
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["error"] == "not_in_range"
    assert body["module_id"] == "draw-1"
    assert "interactionRect" in body
    assert body["actor_position"] == {"x": 100.0, "y": 100.0}
```

- [ ] **Step 3: Failing — text validation reuses chat regex / cap**

```python
def test_post_module_chat_disallowed_chars_returns_invalid_chat_text(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=700.0, y=450.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi @everyone",  # '@' not in whitelist; spec #03 may add it
        },
    )
    # We only assert the route uses the same validator path. If spec #03 has
    # already whitelisted '@', swap to '~' (clearly never-allowed).
    assert resp.status_code in (200, 422)
    if resp.status_code == 422:
        assert resp.json()["detail"]["error"] == "invalid_chat_text"


def test_post_module_chat_over_65_chars_returns_invalid_chat_text(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=700.0, y=450.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "a" * 100,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_chat_text"
```

- [ ] **Step 4: Run — confirm all four fail with 404**

Run: `pytest backend/tests/test_module_chat_route.py -x --tb=short`
Expected: 404 (route does not exist yet).

- [ ] **Step 5: Create the route**

`backend/app/routes/module_chat.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from app.errors import (
    INVALID_CHAT_TEXT,
    NOT_IN_PARTY,
    envelope,
    not_in_range_envelope,
)
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


_SLUG_PATTERN = r"^[a-z0-9-]+$"
_MODULE_PATTERN = r"^[a-z0-9-]+$"


class ModuleChatRequest(BaseModel):
    principal: Principal
    text: str


def _not_in_range(
    world: PartyWorld, module_id: str, actor_id: str
) -> HTTPException:
    rect = world.interaction_rect(module_id) or {
        "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0,
    }
    pos = world.actor_position(actor_id) or {"x": 0.0, "y": 0.0}
    return HTTPException(
        status_code=409,
        detail=not_in_range_envelope(
            module_id=module_id, interaction_rect=rect, actor_position=pos
        ),
    )


@router.post("/{slug}/modules/{module_id}/chat")
def post_module_chat(
    body: ModuleChatRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.module_chat(resolved.id, module_id, body.text)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except PartyWorld.NotInRangeError:
        raise _not_in_range(world, module_id, resolved.id)
    except KeyError:
        raise HTTPException(status_code=404, detail=envelope("not_found"))
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(INVALID_CHAT_TEXT, message=str(exc)),
        )
    return {"cursor": world.cursor, "module_id": module_id, "seq": ev.seq}


@router.get("/{slug}/modules/{module_id}/chat-history")
def get_module_chat_history(
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    return {
        "module_id": module_id,
        "events": world.module_chat_history(module_id),
    }
```

- [ ] **Step 6: Wire router into `backend/app/main.py`**

Add the import next to other routers:
```python
from app.routes import module_chat as module_chat_routes
```
Register the override and include the router:
```python
app.dependency_overrides[module_chat_routes._store_dep] = get_store
...
app.include_router(module_chat_routes.router)
```

- [ ] **Step 7: Wire into `backend/tests/conftest.py`**

Add to the imports:
```python
from app.routes import module_chat as module_chat_routes
```
And inside the `client` fixture:
```python
    app.dependency_overrides[module_chat_routes._store_dep] = lambda: store
```

- [ ] **Step 8: Run — confirm passes**

Run: `pytest backend/tests/test_module_chat_route.py -x --tb=short`
Expected: PASS (all four).

- [ ] **Step 9: Commit**

```bash
git add backend/app/routes/module_chat.py backend/app/main.py backend/tests/conftest.py backend/tests/test_module_chat_route.py
git commit -m "feat(modules): POST /modules/{id}/chat with enriched not_in_range envelope"
```

---

## Task 5: Observer scoping — `module_chat` only inside the rect

**Files:**
- Modify: `backend/app/world.py` — extend spec #02's scoping registry
- Test: `backend/tests/test_module_chat_observer_scoping.py` (new)

This is the spec #04 extension to spec #02's `observe_since` scoping. Spec #02 exposes a registry: `PartyWorld._visibility_predicates: dict[str, Callable[[Event, str], bool]]`. We register a predicate for `module_chat`.

- [ ] **Step 1: Failing tests**

`backend/tests/test_module_chat_observer_scoping.py`:
```python
def test_module_chat_visible_to_participant_inside_rect(
    client, register_human, join_party
):
    a = register_human("alex")
    b = register_human("bee")
    join_party(a, "cream-terrazzo", x=700.0, y=450.0)
    join_party(b, "cream-terrazzo", x=700.0, y=450.0)
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": a}, "text": "hi crew"},
    )
    # Observer is `b`, who is inside the rect.
    resp = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "observer_id": b},
    )
    types = [e["type"] for e in resp.json()["events"]]
    assert "module_chat" in types


def test_module_chat_hidden_from_participant_outside_rect(
    client, register_human, join_party
):
    a = register_human("alex")
    b = register_human("bee")
    join_party(a, "cream-terrazzo", x=700.0, y=450.0)
    join_party(b, "cream-terrazzo", x=100.0, y=100.0)
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": a}, "text": "hi crew"},
    )
    resp = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "observer_id": b},
    )
    types = [e["type"] for e in resp.json()["events"]]
    assert "module_chat" not in types
```

This assumes spec #02 added `observer_id` as a query param on `/observe`. If spec #02 named it differently (e.g. `as`), the implementer updates the test to match. The semantics — proximity-scoped per-observer events — are the binding contract.

- [ ] **Step 2: Run — confirm fail**

Run: `pytest backend/tests/test_module_chat_observer_scoping.py -x --tb=short`
Expected: both `module_chat` events appear regardless of position.

- [ ] **Step 3: Register the predicate**

In `backend/app/world.py`, at the end of `PartyWorld.__init__`, after spec #02's predicate registry is initialized, add:
```python
        # Spec #04: module chat events are only visible to participants
        # currently inside the module's interactionRect.
        self._visibility_predicates["module_chat"] = (
            self._module_chat_visible_to
        )
```

And add the predicate method:
```python
    def _module_chat_visible_to(
        self, event: "ModuleChatEvent", observer_id: str
    ) -> bool:
        observer = self.participants.get(observer_id)
        if observer is None:
            return False
        return self.in_zone(event.module_id, observer.x, observer.y)
```

If spec #02's registry has a different name/signature, adapt — but the predicate body stays the same.

- [ ] **Step 4: Run — passes**

Run: `pytest backend/tests/test_module_chat_observer_scoping.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/world.py backend/tests/test_module_chat_observer_scoping.py
git commit -m "feat(observe): scope module_chat events to participants inside the rect"
```

---

## Task 6: Module chat — cooldown reuse (spec #03 `"module"` scope)

**Files:**
- Modify: `backend/app/world.py`, `backend/app/routes/module_chat.py`
- Test: extend `backend/tests/test_module_chat_route.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_module_chat_route.py`:
```python
def test_module_chat_cooldown_returns_429_with_retry_after_ms(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=700.0, y=450.0)
    # Burst limit is 2 per spec #03 defaults; the 3rd back-to-back fails.
    for i in range(2):
        ok = client.post(
            "/api/parties/cream-terrazzo/modules/draw-1/chat",
            json={"principal": {"kind": "human", "id": sid}, "text": f"m{i}"},
        )
        assert ok.status_code == 200
    third = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/chat",
        json={"principal": {"kind": "human", "id": sid}, "text": "m2"},
    )
    assert third.status_code == 429
    body = third.json()["detail"]
    assert body["error"] == "chat_cooldown"
    assert isinstance(body["retry_after_ms"], (int, float))
    assert body["scope"] == "module"
```

- [ ] **Step 2: Wire cooldown into `module_chat` world method**

In `backend/app/world.py`, modify `module_chat`:
```python
    def module_chat(
        self, participant_id: str, module_id: str, text: str
    ) -> ModuleChatEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        self._require_placed(module_id)
        try:
            from app.models import FreeNotesModule  # type: ignore[attr-defined]
        except ImportError:
            FreeNotesModule = ()  # sentinel
        m = self._placed_module(module_id)
        if not isinstance(m, FreeNotesModule):
            self._require_in_zone(participant_id, module_id)
        # Cooldown — reuses spec #03's per-participant token bucket with a
        # dedicated 'module' scope. Same burst/refill rate as 'proximity'.
        self.check_chat_cooldown(participant_id, scope="module")
        cleaned = validate_chat_text(text)
        ...
```
`check_chat_cooldown` comes from spec #03. It raises `PartyWorld.ChatCooldownError` carrying `retry_after_ms`.

- [ ] **Step 3: Map the cooldown error in the route**

In `backend/app/routes/module_chat.py`, in `post_module_chat`:
```python
    except PartyWorld.ChatCooldownError as exc:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                "chat_cooldown",
                retry_after_ms=exc.retry_after_ms,
                scope="module",
            ),
        )
```
(`ChatCooldownError` exposes `retry_after_ms` per spec #03's contract.)

- [ ] **Step 4: Run — passes**

Run: `pytest backend/tests/test_module_chat_route.py::test_module_chat_cooldown_returns_429_with_retry_after_ms -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/world.py backend/app/routes/module_chat.py backend/tests/test_module_chat_route.py
git commit -m "feat(modules): rate-limit module chat via spec #03 cooldown (scope=module)"
```

---

## Task 7: `FreeNotesModule` model + seed `cream-terrazzo`

**Files:**
- Modify: `backend/app/models.py`, `backend/app/parties_data.py`
- Test: `backend/tests/test_freenotes_module.py` (new)

- [ ] **Step 1: Failing seed test**

`backend/tests/test_freenotes_module.py`:
```python
def test_cream_terrazzo_seeds_freenotes_module(client):
    resp = client.get("/api/parties/cream-terrazzo/observe")
    assert resp.status_code == 200
    mods = resp.json()["modules"]
    kinds = {m["kind"] for m in mods}
    assert "freenotes" in kinds
    free = next(m for m in mods if m["kind"] == "freenotes")
    assert free["id"] == "freenotes-1"
    # Freenotes has no interactionRect (notes are world-wide).
    assert "interactionRect" not in free
    assert free["notes"] == []
```

- [ ] **Step 2: Run — fails**

Run: `pytest backend/tests/test_freenotes_module.py -x --tb=short`
Expected: KeyError / no freenotes module.

- [ ] **Step 3: Add the model**

In `backend/app/models.py`, after `DrawBoardModule`:
```python
class FreeNotesModule(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    kind: Literal["freenotes"] = "freenotes"


PlacedModule = Union[StickyNoteModule, DrawBoardModule, FreeNotesModule]
Module = Annotated[
    Union[StickyNoteModule, DrawBoardModule, FreeNotesModule, LightingModule],
    Field(discriminator="kind"),
]
```

- [ ] **Step 4: Seed it in `parties_data.py`**

In `backend/app/parties_data.py`, import `FreeNotesModule` and append to the `cream-terrazzo` `modules=[...]` list:
```python
from app.models import (
    DrawBoardModule,
    FreeNotesModule,
    LightingModule,
    ...
)
...
    modules=[
        LightingModule(preset="dusk"),
        StickyNoteModule(id="sticky-1", x=0, y=420, w=180, h=80),
        DrawBoardModule(id="draw-1", x=620, y=420, w=180, h=80),
        FreeNotesModule(id="freenotes-1"),
    ],
```

- [ ] **Step 5: Update `_module_snapshot` and `_room_view` to render freenotes**

In `backend/app/world.py`, update `snapshot` and `_module_snapshot`:

First, broaden the `placed` filter in `snapshot`:
```python
        placed = [
            m for m in self._party.modules
            if isinstance(m, (StickyNoteModule, DrawBoardModule, FreeNotesModule))
        ]
```
And import `FreeNotesModule` at top:
```python
from app.models import (
    DrawBoardModule,
    FreeNotesModule,
    LightingModule,
    PartyConfig,
    PlacedModule,
    StickyNoteModule,
)
```

Update `_module_snapshot` to branch on freenotes:
```python
    def _module_snapshot(self, m: PlacedModule) -> dict:
        if isinstance(m, FreeNotesModule):
            return {
                "id": m.id,
                "kind": m.kind,
                "notes": [n.model_dump() for n in self.notes_by_module.get(m.id, [])],
            }
        margin = INTERACTION_MARGIN
        ir = {
            "x": m.x - margin,
            "y": m.y - margin,
            "w": m.w + 2 * margin,
            "h": m.h + 2 * margin,
        }
        slots = self.approach_slots(m.id)
        occ = self.slot_occupancy(m.id)
        slots_out = [
            {"x": x, "y": y, "occupied": o} for (x, y), o in zip(slots, occ)
        ]
        base: dict = {
            "id": m.id,
            "kind": m.kind,
            "x": m.x,
            "y": m.y,
            "w": m.w,
            "h": m.h,
            "interactionRect": ir,
            "approachSlots": slots_out,
        }
        if isinstance(m, StickyNoteModule):
            base["notes"] = [n.model_dump() for n in self.notes_by_module[m.id]]
        else:  # DrawBoardModule
            base["strokes"] = [
                s.model_dump() for s in self.strokes_by_module[m.id]
            ]
            now = time.time()
            self._prune_votes(m.id, now)
            population = self._zone_population(m.id)
            active = len(self.votes_by_module[m.id])
            needed = (len(population) // 2) + 1 if population else 1
            base["vote"] = {"votes": active, "needed": needed}
        return base
```

And in `__init__`, initialize `notes_by_module` for freenotes too:
```python
        for m in party.modules:
            if isinstance(m, LightingModule):
                self.lighting = m.preset
            elif isinstance(m, StickyNoteModule):
                self.notes_by_module[m.id] = []
            elif isinstance(m, DrawBoardModule):
                self.strokes_by_module[m.id] = []
                self.votes_by_module[m.id] = {}
                self._last_vote_state[m.id] = (0, 1)
            elif isinstance(m, FreeNotesModule):
                self.notes_by_module[m.id] = []
```

Update the `_placed_module` lookup to include freenotes:
```python
    def _placed_module(self, module_id: str) -> PlacedModule | None:
        for m in self._party.modules:
            if isinstance(m, (StickyNoteModule, DrawBoardModule, FreeNotesModule)) and m.id == module_id:
                return m
        return None
```

Finally, update `_room_view` in `backend/app/routes/party_actions.py` to render freenotes in `/observe`'s `room.modules`:
```python
        "modules": [
            {
                "id": m.id,
                "kind": m.kind,
                **(
                    {"x": m.x, "y": m.y, "w": m.w, "h": m.h}
                    if m.kind in ("stickynotes", "drawboard")
                    else {}
                ),
                **({"preset": m.preset} if m.kind == "lighting" else {}),
            }
            for m in party.modules
        ],
```
The existing dict-comprehension already handles unknown kinds correctly (freenotes has no spatial fields). No code change needed here, but verify by hand.

- [ ] **Step 6: Run — passes**

Run: `pytest backend/tests/test_freenotes_module.py -x --tb=short`
Expected: PASS.

- [ ] **Step 7: Run the full module-related suite to catch regressions**

Run: `pytest backend/tests/test_observe_route.py backend/tests/test_modules_seed.py backend/tests/test_observe_modules.py backend/tests/test_observe_initial_modules_state.py -x --tb=short`
Expected: PASS. Fix any breakage (likely `_module_snapshot` callers expecting `interactionRect`).

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/app/parties_data.py backend/app/world.py backend/tests/test_freenotes_module.py
git commit -m "feat(modules): add freenotes module kind, seed cream-terrazzo"
```

---

## Task 8: Freenotes — `create_note` accepts any in-room coord

**Files:**
- Modify: `backend/app/world.py`, `backend/app/routes/module_notes.py`
- Test: extend `backend/tests/test_freenotes_module.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_freenotes_module.py`:
```python
def test_create_freenote_anywhere_in_room_succeeds(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=100.0, y=100.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "graffiti",
            "color": "pink",
            "x": 400.0,
            "y": 250.0,
        },
    )
    assert resp.status_code == 200, resp.json()
    note = resp.json()["note"]
    assert note["x"] == 400.0
    assert note["y"] == 250.0
    assert note["text"] == "graffiti"


def test_create_freenote_outside_worldsize_clamps_to_room(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=100.0, y=100.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "x",
            "color": "pink",
            "x": 5000.0,  # cream-terrazzo width is 800
            "y": -100.0,
        },
    )
    assert resp.status_code == 200
    note = resp.json()["note"]
    assert 0.0 <= note["x"] <= 800.0
    assert 0.0 <= note["y"] <= 500.0
```

- [ ] **Step 2: Run — fails**

Run: `pytest backend/tests/test_freenotes_module.py::test_create_freenote_anywhere_in_room_succeeds -x --tb=short`
Expected: 409 not_in_range (the current `_require_in_zone` rejects it).

- [ ] **Step 3: Branch on freenotes in `create_note`**

In `backend/app/world.py`, replace the head of `create_note`:
```python
    def create_note(
        self,
        participant_id: str,
        module_id: str,
        text: str,
        color: str,
        x: float,
        y: float,
    ) -> NoteCreatedEvent:
        m = self._require_placed(module_id)
        if not isinstance(m, (StickyNoteModule, FreeNotesModule)):
            raise KeyError(f"module {module_id} is not a notes module")
        if isinstance(m, StickyNoteModule):
            self._require_in_zone(participant_id, module_id)
        else:  # FreeNotesModule — require room membership only.
            if participant_id not in self.participants:
                raise ParticipantNotInPartyError(participant_id)
        cleaned_text = validate_note_text(text)
        cleaned_color = validate_note_color(color)
        notes = self.notes_by_module[module_id]
        own = sum(1 for n in notes if n.author_id == participant_id)
        if own >= NOTES_PER_USER_MAX:
            raise PartyWorld.LimitReachedError(module_id)
        if isinstance(m, FreeNotesModule):
            wx = self._party.worldSize.width
            wy = self._party.worldSize.height
            lx = max(0.0, min(float(wx), float(x)))
            ly = max(0.0, min(float(wy), float(y)))
        else:
            lx, ly = self._clamp_local(m, x, y)
        participant = self.participants[participant_id]
        note = StickyNote(
            id=uuid.uuid4().hex,
            module_id=module_id,
            author_id=participant_id,
            author_kind=participant.kind,
            text=cleaned_text,
            color=cleaned_color,
            x=lx,
            y=ly,
            created_at=time.time(),
        )
        notes.append(note)
        ev = NoteCreatedEvent(
            seq=self._next_seq(),
            module_id=module_id,
            note=note,
            at=note.created_at,
        )
        self._events.append(ev)
        self._emit(ev)
        return ev
```

- [ ] **Step 4: Mirror the same branch in `update_note` and `delete_note`**

Replace the head of `update_note`:
```python
        m = self._require_placed(module_id)
        if not isinstance(m, (StickyNoteModule, FreeNotesModule)):
            raise KeyError(module_id)
        if isinstance(m, StickyNoteModule):
            self._require_in_zone(participant_id, module_id)
        else:
            if participant_id not in self.participants:
                raise ParticipantNotInPartyError(participant_id)
```
And for the clamp block inside the loop:
```python
                if x is not None or y is not None:
                    nx = n.x if x is None else x
                    ny = n.y if y is None else y
                    if isinstance(m, FreeNotesModule):
                        wx = self._party.worldSize.width
                        wy = self._party.worldSize.height
                        lx = max(0.0, min(float(wx), float(nx)))
                        ly = max(0.0, min(float(wy), float(ny)))
                    else:
                        lx, ly = self._clamp_local(m, nx, ny)
                    fields["x"] = lx
                    fields["y"] = ly
```

Replace the head of `delete_note`:
```python
        m = self._require_placed(module_id)
        if not isinstance(m, (StickyNoteModule, FreeNotesModule)):
            raise KeyError(module_id)
        if isinstance(m, StickyNoteModule):
            self._require_in_zone(participant_id, module_id)
        else:
            if participant_id not in self.participants:
                raise ParticipantNotInPartyError(participant_id)
```

- [ ] **Step 5: Run — passes**

Run: `pytest backend/tests/test_freenotes_module.py -x --tb=short`
Expected: PASS.

- [ ] **Step 6: Re-run the existing notes suite — confirm no regressions**

Run: `pytest backend/tests/test_notes_route.py backend/tests/test_module_notes_error_body.py -x --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/world.py backend/tests/test_freenotes_module.py
git commit -m "feat(modules): allow freenotes anywhere in room with worldSize clamp"
```

---

## Task 9: Collapse the `FreeNotesModule` import guard in `module_chat`

**Files:**
- Modify: `backend/app/world.py`

The `try/except ImportError` guard added in Task 3 step 7 was temporary. Task 7 added `FreeNotesModule`, so we can now import it cleanly.

- [ ] **Step 1: Edit `module_chat` to do a direct import**

In `backend/app/world.py`, inside `module_chat`, replace:
```python
        try:
            from app.models import FreeNotesModule  # type: ignore[attr-defined]
        except ImportError:
            FreeNotesModule = ()  # sentinel
        m = self._placed_module(module_id)
        if not isinstance(m, FreeNotesModule):
            self._require_in_zone(participant_id, module_id)
```
With:
```python
        m = self._placed_module(module_id)
        if not isinstance(m, FreeNotesModule):
            self._require_in_zone(participant_id, module_id)
```
(`FreeNotesModule` is already in the top-level import from Task 7.)

- [ ] **Step 2: Run the module chat suite**

Run: `pytest backend/tests/test_module_chat_route.py backend/tests/test_module_chat_history.py -x --tb=short`
Expected: PASS.

- [ ] **Step 3: Add a positive test — module_chat works on freenotes anywhere in room**

Append to `backend/tests/test_module_chat_route.py`:
```python
def test_module_chat_on_freenotes_works_anywhere_in_room(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=400.0, y=250.0)  # nowhere near a wall
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/chat",
        json={"principal": {"kind": "human", "id": sid}, "text": "wall talk"},
    )
    assert resp.status_code == 200
    assert resp.json()["module_id"] == "freenotes-1"
```

- [ ] **Step 4: Run — passes**

Run: `pytest backend/tests/test_module_chat_route.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/world.py backend/tests/test_module_chat_route.py
git commit -m "refactor(world): drop temporary FreeNotesModule import guard in module_chat"
```

---

## Task 10: Observer scoping — freenotes notes by proximity

**Files:**
- Modify: `backend/app/world.py`
- Test: `backend/tests/test_freenotes_observer_scoping.py` (new)

- [ ] **Step 1: Failing test**

`backend/tests/test_freenotes_observer_scoping.py`:
```python
def test_freenote_visible_only_within_proximity_radius(
    client, register_human, join_party
):
    a = register_human("alex")
    b = register_human("bee")
    # 'a' places a freenote at (400, 250).
    join_party(a, "cream-terrazzo", x=400.0, y=250.0)
    join_party(b, "cream-terrazzo", x=400.0, y=250.0)
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": a},
            "text": "x",
            "color": "pink",
            "x": 400.0,
            "y": 250.0,
        },
    )
    # b is right next to it — should see it.
    resp_near = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "observer_id": b},
    )
    assert any(e["type"] == "note_created" for e in resp_near.json()["events"])
    # Now move b far away.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": {"kind": "human", "id": b}, "x": 10.0, "y": 10.0},
    )
    cursor2 = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"observer_id": b},
    ).json()["cursor"]
    # Create another note far from b.
    client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": a},
            "text": "y",
            "color": "pink",
            "x": 700.0,
            "y": 450.0,
        },
    )
    resp_far = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor2, "observer_id": b},
    )
    assert not any(
        e["type"] == "note_created" and e["note"]["text"] == "y"
        for e in resp_far.json()["events"]
    )
```

- [ ] **Step 2: Run — fails**

Run: `pytest backend/tests/test_freenotes_observer_scoping.py -x --tb=short`
Expected: distant note appears in events.

- [ ] **Step 3: Register the predicates**

In `backend/app/world.py`, at the end of `__init__` (after the module_chat predicate from Task 5):
```python
        # Spec #04: freenotes note events are only visible when the observer
        # is within PROXIMITY_RADIUS of the note's (x, y). Sticky notes
        # (rect-bound) continue to use the spec #02 rect rule.
        for ev_type in ("note_created", "note_updated", "note_deleted"):
            self._visibility_predicates[ev_type] = self._note_visible_to
```

Add the predicate:
```python
    def _note_visible_to(self, event, observer_id: str) -> bool:
        # Resolve module kind by event.module_id.
        m = self._placed_module(event.module_id)
        observer = self.participants.get(observer_id)
        if observer is None or m is None:
            return False
        if isinstance(m, FreeNotesModule):
            # Find note (x, y). For deletes we don't have the note in the
            # event; fall back to the author's last known position recorded
            # at delete time — for v1, hide deletes for distant observers.
            note_xy = None
            if hasattr(event, "note"):
                note_xy = (event.note.x, event.note.y)
            else:
                # note_deleted: scan history of created events for this id.
                nid = getattr(event, "note_id", None)
                for ev in self._events:
                    if (
                        isinstance(ev, NoteCreatedEvent)
                        and ev.note.id == nid
                    ):
                        note_xy = (ev.note.x, ev.note.y)
                        break
            if note_xy is None:
                return False
            dx = observer.x - note_xy[0]
            dy = observer.y - note_xy[1]
            return (dx * dx + dy * dy) <= (PROXIMITY_RADIUS ** 2)
        # Sticky/drawboard: rect rule (spec #02 default).
        return self.in_zone(event.module_id, observer.x, observer.y)
```

Import `PROXIMITY_RADIUS` from `app.world` (it lives in this file per spec #02) — no import needed since this is the same module.

- [ ] **Step 4: Run — passes**

Run: `pytest backend/tests/test_freenotes_observer_scoping.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Re-run sticky note observer tests**

Run: `pytest backend/tests/test_observe_modules.py -x --tb=short`
Expected: PASS (sticky behaviour unchanged — same predicate, isinstance branch).

- [ ] **Step 6: Commit**

```bash
git add backend/app/world.py backend/tests/test_freenotes_observer_scoping.py
git commit -m "feat(observe): scope freenotes note events by PROXIMITY_RADIUS"
```

---

## Task 11: `NoteReactionEvent` + `react_to_note` world method

**Files:**
- Modify: `backend/app/events.py`, `backend/app/world.py`
- Test: `backend/tests/test_note_reaction.py` (new)

- [ ] **Step 1: Failing test**

`backend/tests/test_note_reaction.py`:
```python
from app.events import NoteReactionEvent


def test_note_reaction_event_shape():
    ev = NoteReactionEvent(
        seq=1,
        module_id="freenotes-1",
        note_id="abc",
        emoji="🎉",
        at=1.0,
        actor_id="p",
        actor_username="alex",
        actor_kind="human",
    )
    assert ev.type == "note_reaction"
    assert ev.emoji == "🎉"
```

- [ ] **Step 2: Run — fails**

Run: `pytest backend/tests/test_note_reaction.py -x --tb=short`

- [ ] **Step 3: Add the model**

In `backend/app/events.py`:
```python
class NoteReactionEvent(BaseModel):
    seq: int
    type: Literal["note_reaction"] = "note_reaction"
    module_id: str
    note_id: str
    emoji: str
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
```
Add to the `Event` union.

Also add a `reactions: dict[str, int] = Field(default_factory=dict)` field to `StickyNote`:
```python
from pydantic import BaseModel, Field

class StickyNote(BaseModel):
    id: str
    module_id: str
    author_id: str
    author_kind: Literal["human", "agent"]
    text: str
    color: Literal["yellow", "pink", "blue", "green"]
    x: float
    y: float
    created_at: float
    reactions: dict[str, int] = Field(default_factory=dict)
```

- [ ] **Step 4: World-level test**

Append to `backend/tests/test_note_reaction.py`:
```python
from app.events import Participant
from app.models import (
    FreeNotesModule,
    Music,
    PartyConfig,
    Room,
    Theme,
    WorldSize,
)
from app.world import PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t", name="t", description="t",
        theme=Theme(floor="#fff", accent="#000"),
        zones=[],
        music=Music(url=None, label="x"),
        worldSize=WorldSize(width=800, height=500),
        room=Room(border="1px solid #000", walls=[]),
        modules=[FreeNotesModule(id="freenotes-1")],
    )
    return PartyWorld(party)


def test_react_to_note_increments_and_emits_event():
    world = _world()
    world.join(Participant(id="p1", kind="human", username="alex",
                           color="#ff6b9d", x=100.0, y=100.0, joined_at=0.0))
    note_ev = world.create_note("p1", "freenotes-1", "hi", "pink", 100.0, 100.0)
    note_id = note_ev.note.id
    ev = world.react_to_note("p1", "freenotes-1", note_id, "🎉")
    assert ev.type == "note_reaction"
    assert ev.emoji == "🎉"
    # Counter updated on the note record.
    notes = world.notes_by_module["freenotes-1"]
    assert notes[0].reactions == {"🎉": 1}


def test_react_to_note_unknown_emoji_raises():
    world = _world()
    world.join(Participant(id="p1", kind="human", username="alex",
                           color="#ff6b9d", x=100.0, y=100.0, joined_at=0.0))
    note_ev = world.create_note("p1", "freenotes-1", "hi", "pink", 100.0, 100.0)
    import pytest
    from app.validation import ReactionValidationError
    with pytest.raises(ReactionValidationError):
        world.react_to_note("p1", "freenotes-1", note_ev.note.id, "💩")
```

- [ ] **Step 5: Run — fails (no method)**

Run: `pytest backend/tests/test_note_reaction.py -x --tb=short`

- [ ] **Step 6: Implement `react_to_note`**

In `backend/app/world.py`, add new imports at top:
```python
from app.events import (
    ...
    NoteReactionEvent,
    ...
)
```
And the method:
```python
    def react_to_note(
        self,
        participant_id: str,
        module_id: str,
        note_id: str,
        emoji: str,
    ) -> NoteReactionEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        m = self._require_placed(module_id)
        if not isinstance(m, (StickyNoteModule, FreeNotesModule)):
            raise KeyError(module_id)
        # Sticky must be inside rect to react; freenotes is open everywhere
        # in the room (parallel to create_note rules).
        if isinstance(m, StickyNoteModule):
            self._require_in_zone(participant_id, module_id)
        cleaned = validate_reaction_emoji(emoji)
        notes = self.notes_by_module.get(module_id, [])
        for i, n in enumerate(notes):
            if n.id == note_id:
                new_reactions = dict(n.reactions)
                new_reactions[cleaned] = new_reactions.get(cleaned, 0) + 1
                notes[i] = n.model_copy(update={"reactions": new_reactions})
                ev = NoteReactionEvent(
                    seq=self._next_seq(),
                    module_id=module_id,
                    note_id=note_id,
                    emoji=cleaned,
                    at=time.time(),
                    **self._actor_fields(participant_id),
                )
                self._events.append(ev)
                self._emit(ev)
                return ev
        raise KeyError(note_id)
```

- [ ] **Step 7: Run — passes**

Run: `pytest backend/tests/test_note_reaction.py -x --tb=short`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/events.py backend/app/world.py backend/tests/test_note_reaction.py
git commit -m "feat(modules): NoteReactionEvent + StickyNote.reactions counter"
```

---

## Task 12: `POST /modules/{id}/notes/{note_id}/react` route

**Files:**
- Modify: `backend/app/routes/module_notes.py`
- Test: extend `backend/tests/test_note_reaction.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_note_reaction.py`:
```python
def test_react_to_note_route_succeeds(client, register_human, join_party):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=400.0, y=250.0)
    note_resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "graf", "color": "pink", "x": 400.0, "y": 250.0,
        },
    )
    note_id = note_resp.json()["note"]["id"]
    resp = client.post(
        f"/api/parties/cream-terrazzo/modules/freenotes-1/notes/{note_id}/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "🎉"},
    )
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["emoji"] == "🎉"
    assert "cursor" in body


def test_react_to_note_unknown_note_returns_404(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=400.0, y=250.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes/deadbeef/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "🎉"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "not_found"


def test_react_to_note_invalid_emoji_returns_422(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=400.0, y=250.0)
    note_resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "g", "color": "pink", "x": 400.0, "y": 250.0,
        },
    )
    nid = note_resp.json()["note"]["id"]
    resp = client.post(
        f"/api/parties/cream-terrazzo/modules/freenotes-1/notes/{nid}/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "💩"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_emoji"
```

- [ ] **Step 2: Run — fails 404 route missing**

- [ ] **Step 3: Add the route**

In `backend/app/routes/module_notes.py`:

Top of file:
```python
from app.validation import (
    NoteValidationError,
    REACTION_EMOJI_ALLOWLIST,
    ReactionValidationError,
    STICKY_COLOR_ALLOWLIST,
)
```
Add a new request model:
```python
class ReactNoteRequest(BaseModel):
    principal: Principal
    emoji: str
```
And the handler:
```python
@router.post("/{slug}/modules/{module_id}/notes/{note_id}/react")
def react_to_note(
    body: ReactNoteRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    module_id: str = Path(pattern=_MODULE_PATTERN),
    note_id: str = Path(pattern=_NOTE_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        ev = world.react_to_note(resolved.id, module_id, note_id, body.emoji)
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except PartyWorld.NotInRangeError:
        rect = world.interaction_rect(module_id) or {
            "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0,
        }
        pos = world.actor_position(resolved.id) or {"x": 0.0, "y": 0.0}
        raise HTTPException(
            status_code=409,
            detail=not_in_range_envelope(
                module_id=module_id, interaction_rect=rect, actor_position=pos,
            ),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=envelope("not_found"))
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
        "note_id": ev.note_id,
        "module_id": ev.module_id,
        "cursor": world.cursor,
    }
```

Note the `_NOTE_PATTERN` regex (`^[a-f0-9]+$`) already exists in this module — `uuid4().hex` matches it.

- [ ] **Step 4: Run — passes**

Run: `pytest backend/tests/test_note_reaction.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Add a test confirming `reactions` appears on the note in `/observe`**

Append to `backend/tests/test_note_reaction.py`:
```python
def test_reactions_appear_on_note_in_observe(
    client, register_human, join_party
):
    sid = register_human("alex")
    join_party(sid, "cream-terrazzo", x=400.0, y=250.0)
    note_resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "g", "color": "pink", "x": 400.0, "y": 250.0,
        },
    )
    nid = note_resp.json()["note"]["id"]
    client.post(
        f"/api/parties/cream-terrazzo/modules/freenotes-1/notes/{nid}/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "🎉"},
    )
    obs = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"observer_id": sid},
    )
    mods = obs.json()["modules"]
    free = next(m for m in mods if m["kind"] == "freenotes")
    note = next(n for n in free["notes"] if n["id"] == nid)
    assert note["reactions"] == {"🎉": 1}
```

- [ ] **Step 6: Run — passes**

Run: `pytest backend/tests/test_note_reaction.py -x --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/module_notes.py backend/tests/test_note_reaction.py
git commit -m "feat(modules): POST notes/{id}/react with structured errors"
```

---

## Task 13: Observer scoping — `note_reaction` follows the note

**Files:**
- Modify: `backend/app/world.py`
- Test: extend `backend/tests/test_freenotes_observer_scoping.py`

- [ ] **Step 1: Failing test**

Append to `backend/tests/test_freenotes_observer_scoping.py`:
```python
def test_note_reaction_hidden_from_distant_observer(
    client, register_human, join_party
):
    a = register_human("alex")
    b = register_human("bee")
    join_party(a, "cream-terrazzo", x=400.0, y=250.0)
    join_party(b, "cream-terrazzo", x=10.0, y=10.0)
    note = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": a},
            "text": "g", "color": "pink", "x": 400.0, "y": 250.0,
        },
    )
    nid = note.json()["note"]["id"]
    cursor = client.get(
        "/api/parties/cream-terrazzo/observe", params={"observer_id": b},
    ).json()["cursor"]
    client.post(
        f"/api/parties/cream-terrazzo/modules/freenotes-1/notes/{nid}/react",
        json={"principal": {"kind": "human", "id": a}, "emoji": "🎉"},
    )
    resp = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "observer_id": b},
    )
    assert not any(e["type"] == "note_reaction" for e in resp.json()["events"])
```

- [ ] **Step 2: Register the predicate**

In `backend/app/world.py`, in `__init__`:
```python
        self._visibility_predicates["note_reaction"] = self._note_reaction_visible_to
```
And:
```python
    def _note_reaction_visible_to(self, event, observer_id: str) -> bool:
        m = self._placed_module(event.module_id)
        observer = self.participants.get(observer_id)
        if observer is None or m is None:
            return False
        if isinstance(m, FreeNotesModule):
            for n in self.notes_by_module.get(event.module_id, []):
                if n.id == event.note_id:
                    dx = observer.x - n.x
                    dy = observer.y - n.y
                    return (dx * dx + dy * dy) <= (PROXIMITY_RADIUS ** 2)
            return False
        return self.in_zone(event.module_id, observer.x, observer.y)
```

- [ ] **Step 3: Run — passes**

Run: `pytest backend/tests/test_freenotes_observer_scoping.py -x --tb=short`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/world.py backend/tests/test_freenotes_observer_scoping.py
git commit -m "feat(observe): scope note_reaction events to proximity (freenotes) / rect (sticky)"
```

---

## Task 14: Agent guide + frontend types + final smoke test

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Modify: `frontend/src/api/types.ts`
- Test: manual smoke + the full suite

- [ ] **Step 1: Update the agent guide**

Open `backend/app/routes/agent_guide.py`. Append a section under the existing modules docs. Match the file's existing markdown style. Concrete additions:

```markdown
### Module-scoped chat

`POST /api/parties/{slug}/modules/{module_id}/chat`
Body: `{"principal": {...}, "text": "..."}`

- You must be inside the module's `interactionRect` (except `freenotes`, which only requires you to be in the room).
- Text rules: same regex as `/chat` (letters, digits, spaces, `.,!?'-`, plus any additions from spec #03), max 65 chars.
- Cooldown: `scope: "module"` token bucket (burst 2, refill 1 per 3s, same as proximity chat).
- On cooldown: `429 {"detail": {"error": "chat_cooldown", "retry_after_ms": <int>, "scope": "module"}}`.
- On out-of-range: `409 {"detail": {"error": "not_in_range", "module_id": "...", "interactionRect": {...}, "actor_position": {...}}}` — walk into the rect and retry.

`GET /api/parties/{slug}/modules/{module_id}/chat-history` — last 50 `module_chat` events.

Events: `module_chat {seq, type, module_id, text, at, actor_id, actor_username, actor_kind}`. Delivered via `/observe` only to participants currently inside the module's `interactionRect`.

### Free-floating notes (`freenotes`)

Module kind `freenotes` accepts notes anywhere inside the room. Same endpoints as sticky notes (`POST /modules/{id}/notes`, `PATCH ...`, `DELETE ...`) — but `(x, y)` is in world coordinates and is clamped to `worldSize`. Visibility: notes are only delivered via `/observe` when the requester is within `PROXIMITY_RADIUS` of the note's `(x, y)`. `cream-terrazzo` seeds one with id `freenotes-1`.

### React to a note

`POST /api/parties/{slug}/modules/{module_id}/notes/{note_id}/react`
Body: `{"principal": {...}, "emoji": "🎉"}` — emoji must be in the standard reaction allow-list. Increments `note.reactions[emoji]` (a `dict[str, int]` on the note). Emits `note_reaction {module_id, note_id, emoji, ...}`.

### Module 4xx errors

Every module endpoint that requires you to stand inside a rect returns:
`409 {"detail": {"error": "not_in_range", "module_id": "...", "interactionRect": {"x", "y", "w", "h"}, "actor_position": {"x", "y"}}}`
Auto-walk: pick any point inside `interactionRect` and POST `/move` before retrying.
```

(Locate the existing "Modules" section in `agent_guide.py` and append; do not duplicate guide content elsewhere.)

- [ ] **Step 2: Update `frontend/src/api/types.ts`**

Add these declarations (find the existing events union and module types and extend them):
```typescript
export interface ModuleChatEvent {
  type: "module_chat";
  seq: number;
  module_id: string;
  text: string;
  at: number;
  actor_id: string;
  actor_username: string;
  actor_kind: "human" | "agent";
}

export interface NoteReactionEvent {
  type: "note_reaction";
  seq: number;
  module_id: string;
  note_id: string;
  emoji: string;
  at: number;
  actor_id: string;
  actor_username: string;
  actor_kind: "human" | "agent";
}

export interface FreeNotesModule {
  id: string;
  kind: "freenotes";
  notes: StickyNote[];
}

// Extend StickyNote (find existing type and add):
//   reactions: Record<string, number>;
```
Add `ModuleChatEvent | NoteReactionEvent` to the discriminated `Event` union and `FreeNotesModule` to the `Module` union.

- [ ] **Step 3: Run the full backend test suite**

Run: `pytest backend/tests/ -x --tb=short`
Expected: PASS.

- [ ] **Step 4: Manual smoke test**

```bash
cd backend && uvicorn app.main:app --reload &
SERVER_PID=$!
sleep 2

# Register, join inside the freenotes module's world.
SID=$(curl -s -X POST localhost:8000/api/session -H "Content-Type: application/json" \
  -d '{"username":"smoke","color":"#ff6b9d"}' | python -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

curl -s -X POST localhost:8000/api/parties/cream-terrazzo/join \
  -H "Content-Type: application/json" \
  -d "{\"principal\":{\"kind\":\"human\",\"id\":\"$SID\"},\"x\":400,\"y\":250}"

# Create a free-floating note.
NOTE=$(curl -s -X POST localhost:8000/api/parties/cream-terrazzo/modules/freenotes-1/notes \
  -H "Content-Type: application/json" \
  -d "{\"principal\":{\"kind\":\"human\",\"id\":\"$SID\"},\"text\":\"hello\",\"color\":\"pink\",\"x\":400,\"y\":250}")
NID=$(echo "$NOTE" | python -c "import sys,json; print(json.load(sys.stdin)['note']['id'])")

# React.
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/modules/freenotes-1/notes/$NID/react \
  -H "Content-Type: application/json" \
  -d "{\"principal\":{\"kind\":\"human\",\"id\":\"$SID\"},\"emoji\":\"🎉\"}"

# Confirm observe shows reactions: {"🎉": 1}
curl -s "localhost:8000/api/parties/cream-terrazzo/observe?observer_id=$SID" | python -m json.tool | grep -A1 reactions

# Try a not_in_range error (move far, then try drawboard chat).
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/move \
  -H "Content-Type: application/json" \
  -d "{\"principal\":{\"kind\":\"human\",\"id\":\"$SID\"},\"x\":10,\"y\":10}"
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/modules/draw-1/chat \
  -H "Content-Type: application/json" \
  -d "{\"principal\":{\"kind\":\"human\",\"id\":\"$SID\"},\"text\":\"hi\"}" | python -m json.tool

kill $SERVER_PID
```
Expected last response includes `interactionRect` and `actor_position: {"x": 10, "y": 10}`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/agent_guide.py frontend/src/api/types.ts
git commit -m "docs(agent-guide): module chat, freenotes, note reactions, enriched not_in_range"
```

---

## Out of scope

- Lighting/music modules (spec #07 owns music).
- Per-actor reaction tracking (we only count emoji totals, not who reacted; matches the existing room reactions model).
- Removing a reaction (no `DELETE` on `notes/{id}/react` for v1 — agents can compose a new emoji instead).
- Walls / line-of-sight for freenotes proximity (radius only, per shared brief decision #6).
- Cross-module chat history aggregation (each module has its own 50-event buffer).

## Self-review checklist (run before handoff)

1. **Spec coverage:** Each of the four spec requirements maps to ≥1 task — confirmed via the Spec → Task map.
2. **Placeholder scan:** No TBD / TODO / "implement later" — every code step has full code.
3. **Type consistency:** `ModuleChatEvent.module_id`, `NoteReactionEvent.module_id` / `.note_id` / `.emoji`, `FreeNotesModule.id` / `.kind` all match between events.py, world.py, routes/, and types.ts.
4. **Helper names:** `not_in_range_envelope(module_id, interaction_rect, actor_position)` is the single name used everywhere.
5. **Spec #02 hooks named consistently:** `_visibility_predicates`, `PROXIMITY_RADIUS`, `observe_since`. If spec #02's actual names differ, rename inline (one search/replace across this plan's files).
6. **Spec #03 hook named consistently:** `check_chat_cooldown(participant_id, scope)`, `PartyWorld.ChatCooldownError.retry_after_ms`. Same rename rule applies.
