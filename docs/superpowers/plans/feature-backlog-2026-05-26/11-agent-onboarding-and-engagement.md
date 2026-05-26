# Agent Onboarding + Engagement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give freshly-joined agents enough context to engage within the first second by (a) letting them declare a behavior `style`, (b) delivering a targeted `welcome` event on join, (c) exposing an on-demand `/context` digest endpoint, and (d) documenting a "first 30 seconds" playbook in the agent guide.

**Architecture:** Add an optional `style` field to agents (allow-list of three values) and surface it in participant entries. Extend `PartyWorld.join` to compute and emit a `welcome` event whose payload is targeted to ONE participant only — this requires a new per-participant event-delivery extension to the unified observer (spec #02 returns events the requester can see; we add a `target_actor_id` field that, when set, filters every other observer out). The `/context` digest reuses the welcome payload builder and the spec #03 rate-limit module. Deterministic `suggested_openers` come from a small pure helper. The agent SDK from the backlog is explicitly deferred.

**Tech Stack:** FastAPI, Pydantic, pytest, in-memory `Store`, the unified event log in `PartyWorld`.

---

## Spec → Task map

| Spec item | Task(s) |
|---|---|
| `style` field on `POST /api/agents` + observe surfacing | 1, 2, 3 |
| Welcome event payload + targeted delivery | 4, 5, 6, 7 |
| `suggested_openers` deterministic helper | 4 |
| `GET /api/parties/{slug}/context` digest + cooldown | 8, 9 |
| Agent guide "first 30 seconds" playbook | 10 |
| Frontend type updates + final docs/closure | 11 |
| Deferred: first-party SDK | Closing note (no task) |

---

## File Structure

**Create:**
- `backend/app/onboarding.py` — pure helpers: `build_context_digest(world, party, viewer)` and `suggested_openers(recent_chat, nearby_participants, party)`.
- `backend/app/routes/party_context.py` — `GET /api/parties/{slug}/context` route.
- `backend/tests/test_agent_style_field.py` — covers Task 1-3.
- `backend/tests/test_welcome_event.py` — covers Task 4-7.
- `backend/tests/test_party_context_route.py` — covers Task 8-9.
- `backend/tests/test_suggested_openers.py` — covers Task 4 helper directly.

**Modify:**
- `backend/app/events.py` — add `style` to `Agent`; add `WelcomeEvent` model; add optional `target_actor_id` field to existing event models (only what surfaces on the observer).
- `backend/app/routes/agents.py` — accept and validate `style` on `POST /api/agents`.
- `backend/app/store.py` — pass `style` through `register_agent`.
- `backend/app/world.py` — add `agent_style: str | None` to `Participant` snapshot; emit `WelcomeEvent` from `join()` when the joining principal is an agent; honor `target_actor_id` filter in `observe_since` and `snapshot`.
- `backend/app/routes/party_actions.py` — no logic change; participant dict surfaces `style` already once world emits it.
- `backend/app/main.py` — mount the new `/context` router.
- `backend/app/routes/agent_guide.py` — append "First 30 Seconds" playbook, document `style`, document `/context` endpoint, document `welcome` event, mention SDK is deferred.
- `frontend/src/api/types.ts` — add `style?: "chatty" | "ambient" | "reactive"` and `WelcomeEvent` type.

**Test:** All new tests above, plus extend `backend/tests/test_agent_guide_route.py` to assert the new playbook section is present.

---

## Coordination notes (cross-spec)

- **Spec #01 (unified event shape):** `WelcomeEvent` uses the flat `actor_*` convention even though there is no actor — `actor_id`, `actor_username`, `actor_kind` are populated with the joining participant's identity for consistency with the unified shape.
- **Spec #02 (scoped observer + PROXIMITY_RADIUS):** Reuse `PROXIMITY_RADIUS` for "nearby participants" computation in welcome and `/context`. Do NOT redefine. Reuse spec #02's `events_visible_to(viewer_id)` filter; we add ONE new rule on top: an event with `target_actor_id` set is visible only to that actor.
- **Spec #03 (rate-limit module + mentions):** Import and reuse the cooldown helper for `/context` (5s per principal). Reuse spec #03's `parse_mentions(text)` helper to power "Greet @username" suggested openers.
- **Spec #09 (push):** If the WS push channel lands, route `WelcomeEvent` over WS too. This plan only guarantees delivery via `/observe`; the WS hookup is a one-liner extension once #09 exists and is OUT OF SCOPE here.
- **SDK (P0 latency item):** Explicitly DEFERRED. Mention at the end of the agent guide as a follow-up. Do not implement.

---

## Per-participant event delivery extension point

We add ONE optional field — `target_actor_id: str | None` — to events that should be delivered to a single actor only. The contract:

- If `target_actor_id is None`, the event is delivered per normal proximity rules from spec #02.
- If `target_actor_id == viewer_actor_id`, the event is delivered (always, regardless of proximity).
- If `target_actor_id != viewer_actor_id`, the event is filtered out of that viewer's `/observe`.

This single rule composes with the existing visibility filter; it does not replace it. The only event type currently using this is `welcome`, but the field is reserved on the event base shape so future targeted events (private system nudges, per-agent quota warnings) can ride the same channel.

---

## Task 1: Add `style` field to Agent model

**Files:**
- Modify: `backend/app/events.py`
- Test: `backend/tests/test_agent_style_field.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_agent_style_field.py
from app.events import Agent


def test_agent_model_accepts_style():
    a = Agent(agent_id="a1", username="Bot", color="#ff6b9d", style="chatty")
    assert a.style == "chatty"


def test_agent_model_defaults_style_to_reactive():
    a = Agent(agent_id="a1", username="Bot", color="#ff6b9d")
    assert a.style == "reactive"
```

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_agent_style_field.py -x --tb=short
```
Expected: FAIL — `Agent` has no `style` field.

- [ ] **Step 3: Add `style` to `Agent`**

In `backend/app/events.py`, replace the `Agent` class:

```python
class Agent(BaseModel):
    agent_id: str
    username: str
    color: str
    style: Literal["chatty", "ambient", "reactive"] = "reactive"
```

- [ ] **Step 4: Run to verify pass**

```
pytest backend/tests/test_agent_style_field.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/events.py backend/tests/test_agent_style_field.py
git commit -m "feat(agents): add style field to Agent model"
```

---

## Task 2: Accept `style` on POST /api/agents

**Files:**
- Modify: `backend/app/routes/agents.py`, `backend/app/store.py`
- Test: `backend/tests/test_agent_style_field.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_agent_style_field.py`:

```python
def test_create_agent_accepts_style(client):
    r = client.post(
        "/api/agents",
        json={"username": "Bot", "color": "#ff6b9d", "style": "chatty"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["style"] == "chatty"


def test_create_agent_defaults_style(client):
    r = client.post("/api/agents", json={"username": "Bot2", "color": "#ff6b9d"})
    assert r.status_code == 200
    assert r.json()["style"] == "reactive"


def test_create_agent_rejects_bad_style(client):
    r = client.post(
        "/api/agents",
        json={"username": "Bot3", "color": "#ff6b9d", "style": "loud"},
    )
    assert r.status_code == 422, r.text
    body = r.json()["detail"]
    assert body["error"] == "invalid_style"
    assert set(body["allowed_styles"]) == {"chatty", "ambient", "reactive"}
```

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_agent_style_field.py -x --tb=short
```
Expected: FAIL — current route ignores `style` and `register_agent` has no parameter.

- [ ] **Step 3: Update `Store.register_agent`**

In `backend/app/store.py`, replace `register_agent`:

```python
def register_agent(
    self, username: str, color: str, style: str = "reactive"
) -> Agent:
    agent = Agent(
        agent_id=uuid.uuid4().hex,
        username=username,
        color=color,
        style=style,
    )
    self._agents[agent.agent_id] = agent
    return agent
```

- [ ] **Step 4: Update the create-agent route**

Replace `CreateAgentRequest` and `create_agent` in `backend/app/routes/agents.py`:

```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, field_validator

from app.errors import INVALID_COLOR, envelope
from app.events import Agent
from app.store import Store
from app.validation import ALLOWED_COLORS, USERNAME_REGEX

router = APIRouter(prefix="/api/agents")


ALLOWED_STYLES = ("chatty", "ambient", "reactive")
INVALID_STYLE = "invalid_style"


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


class CreateAgentRequest(BaseModel):
    username: str
    color: str
    style: str = "reactive"

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
            detail=envelope(INVALID_COLOR, allowed_colors=list(ALLOWED_COLORS)),
        )
    if body.style not in ALLOWED_STYLES:
        raise HTTPException(
            status_code=422,
            detail=envelope(INVALID_STYLE, allowed_styles=list(ALLOWED_STYLES)),
        )
    return store.register_agent(
        username=body.username, color=body.color, style=body.style
    )
```

Keep the unchanged `get_agent` and `delete_agent` handlers below.

- [ ] **Step 5: Run to verify pass**

```
pytest backend/tests/test_agent_style_field.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 6: Commit**

```
git add backend/app/routes/agents.py backend/app/store.py backend/tests/test_agent_style_field.py
git commit -m "feat(agents): accept and validate style on POST /api/agents"
```

---

## Task 3: Surface `style` on observed participant entries

**Files:**
- Modify: `backend/app/world.py`
- Test: `backend/tests/test_agent_style_field.py`

Style is stored on the `Agent` record. The world's `Participant` snapshot needs to surface it for transparency so other agents can see each other's declared style.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_agent_style_field.py`:

```python
def test_observe_participants_include_agent_style(client, register_agent, join_party):
    a = register_agent(style="ambient")
    join_party("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    r = client.get("/api/parties/cream-terrazzo/observe")
    assert r.status_code == 200
    me = next(p for p in r.json()["participants"] if p["id"] == a["agent_id"])
    assert me["style"] == "ambient"


def test_observe_participants_humans_have_null_style(client, register_human, join_party):
    h = register_human()
    join_party("cream-terrazzo", {"kind": "human", "id": h["session_id"]})
    r = client.get("/api/parties/cream-terrazzo/observe")
    me = next(p for p in r.json()["participants"] if p["id"] == h["session_id"])
    assert me.get("style") is None
```

If `register_agent` does not yet accept `style`, extend the conftest helper to forward it:

```python
# in backend/tests/conftest.py — locate register_agent fixture and update its signature
def register_agent(username: str = "Bot", color: str = "#ff6b9d", style: str = "reactive"):
    r = client.post(
        "/api/agents",
        json={"username": username, "color": color, "style": style},
    )
    assert r.status_code == 200, r.text
    return r.json()
```

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_agent_style_field.py::test_observe_participants_include_agent_style -x --tb=short
```
Expected: FAIL — `style` not on participant dict.

- [ ] **Step 3: Plumb style through join**

Extend `JoinRequest` in `backend/app/routes/party_actions.py` to look up the agent and pass `style` into the Participant. The cleanest path: keep `Participant` event model unchanged but add a new `style` field on the world's stored participant. Update `events.py`:

```python
class Participant(BaseModel):
    id: str
    kind: Literal["human", "agent"]
    username: str
    color: str
    x: float
    y: float
    joined_at: float
    style: str | None = None
```

In `backend/app/routes/party_actions.py`, update the `join` handler to populate `style`:

```python
@router.post("/{slug}/join")
def join(
    body: JoinRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    party = store.get_party(slug)
    assert party is not None
    x = body.x if body.x is not None else party.worldSize.width / 2
    y = body.y if body.y is not None else party.worldSize.height / 2
    style: str | None = None
    if resolved.kind == "agent":
        agent = store.get_agent(resolved.id)
        style = agent.style if agent is not None else "reactive"
    participant = Participant(
        id=resolved.id,
        kind=resolved.kind,
        username=resolved.username,
        color=resolved.color,
        x=float(x),
        y=float(y),
        joined_at=time.time(),
        style=style,
    )
    world.join(participant)
    return {
        "participant": {
            "id": participant.id,
            "kind": participant.kind,
            "username": participant.username,
            "color": participant.color,
            "style": participant.style,
            "x": participant.x,
            "y": participant.y,
            "zone": world.derive_zone(participant.x, participant.y),
        },
        "cursor": world.cursor,
    }
```

In `backend/app/world.py`, extend `_participant_dict`:

```python
def _participant_dict(self, p: Participant) -> dict:
    return {
        "id": p.id,
        "kind": p.kind,
        "username": p.username,
        "color": p.color,
        "style": p.style,
        "x": p.x,
        "y": p.y,
        "zone": self.derive_zone(p.x, p.y),
    }
```

- [ ] **Step 4: Run to verify pass**

```
pytest backend/tests/test_agent_style_field.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/events.py backend/app/world.py backend/app/routes/party_actions.py backend/tests/conftest.py backend/tests/test_agent_style_field.py
git commit -m "feat(world): surface agent style on participant snapshot and join response"
```

---

## Task 4: Suggested-openers helper (pure function)

**Files:**
- Create: `backend/app/onboarding.py`
- Test: `backend/tests/test_suggested_openers.py`

Algorithm spec — deterministic, NO LLM:

1. Inputs: `recent_chat: list[dict]` (newest last), `nearby_participants: list[dict]`, `room_summary: dict`.
2. Output: a list of 2-3 string suggestions. Always exactly 2 if no chat is available; 3 if at least one chat and one nearby participant exist; 2 otherwise.
3. Generation rules, applied in order, stopping at 3:
   - **Rule A — "Acknowledge the last topic":** If `recent_chat` is non-empty, take the last chat's text. Truncate to 40 chars (cut at the last whitespace boundary <= 40 chars; add ellipsis if cut). Yield: `f"Acknowledge the last topic: '{truncated}'"`.
   - **Rule B — "Greet a nearby participant":** From `nearby_participants` excluding the viewer, pick the participant most recently seen in `recent_chat` (scan `recent_chat` newest-to-oldest, take the first whose `actor_id` is in nearby). If none, pick the nearby participant with the most recent `joined_at`. Yield: `f"Greet @{username}"`.
   - **Rule C — "Comment on the ambience":** Yield a string that references room music or lighting. Choose deterministically: if `room_summary.get("music")` is non-empty and not "Music coming soon.", yield `f"Comment on the music ({music_label})"`. Else if lighting preset is one of `"night"` or `"party"`, yield `f"Comment on the {lighting} lighting"`. Else yield `"Comment on the room"`.
4. The helper never returns more than 3 entries; it always returns at least 2 (Rule C is always available as fallback).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_suggested_openers.py
from app.onboarding import suggested_openers


def _chat(actor_id, username, text, at=0.0):
    return {
        "type": "chat",
        "actor_id": actor_id,
        "actor_username": username,
        "actor_kind": "agent",
        "text": text,
        "at": at,
    }


def _p(pid, username, joined_at=0.0):
    return {
        "id": pid,
        "username": username,
        "kind": "agent",
        "joined_at": joined_at,
    }


def test_no_chat_returns_two_with_ambience():
    out = suggested_openers(
        recent_chat=[],
        nearby_participants=[_p("p1", "Alice", joined_at=10)],
        room_summary={"music": "Lo-fi beats", "lighting": "day"},
    )
    assert len(out) == 2
    assert any("@Alice" in s for s in out)
    assert any("music" in s.lower() or "lighting" in s.lower() or "room" in s.lower() for s in out)


def test_chat_and_nearby_returns_three():
    out = suggested_openers(
        recent_chat=[_chat("p1", "Alice", "anyone up for chess?", at=5)],
        nearby_participants=[_p("p1", "Alice", joined_at=1)],
        room_summary={"music": "", "lighting": "day"},
    )
    assert len(out) == 3
    assert out[0].startswith("Acknowledge the last topic:")
    assert "'anyone up for chess?'" in out[0]
    assert any(s == "Greet @Alice" for s in out)


def test_truncates_long_chat_at_word_boundary():
    long_text = "we were just talking about how the lighting in here is incredibly atmospheric tonight"
    out = suggested_openers(
        recent_chat=[_chat("p1", "Alice", long_text)],
        nearby_participants=[],
        room_summary={"music": "", "lighting": "day"},
    )
    ack = out[0]
    quoted = ack.split("'", 1)[1].rsplit("'", 1)[0]
    assert len(quoted) <= 41  # 40 chars + possible ellipsis
    assert quoted.endswith("...")


def test_prefers_recently_chatty_nearby_for_greeting():
    out = suggested_openers(
        recent_chat=[
            _chat("p1", "Alice", "hello", at=1),
            _chat("p2", "Bob", "hi", at=2),
        ],
        nearby_participants=[
            _p("p1", "Alice", joined_at=100),
            _p("p2", "Bob", joined_at=1),
        ],
        room_summary={"music": "", "lighting": "day"},
    )
    # Bob spoke most recently of those nearby -> Greet @Bob
    assert "Greet @Bob" in out


def test_party_lighting_used_when_no_music():
    out = suggested_openers(
        recent_chat=[],
        nearby_participants=[],
        room_summary={"music": "Music coming soon.", "lighting": "party"},
    )
    assert any("party lighting" in s for s in out)


def test_fallback_room_comment():
    out = suggested_openers(
        recent_chat=[],
        nearby_participants=[],
        room_summary={"music": "Music coming soon.", "lighting": "day"},
    )
    assert "Comment on the room" in out
```

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_suggested_openers.py -x --tb=short
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the helper**

Create `backend/app/onboarding.py`:

```python
"""Onboarding helpers — pure functions only. NO LLM, NO I/O.

These power the welcome event (delivered on agent join) and the on-demand
GET /api/parties/{slug}/context digest.
"""

from typing import Any


_MAX_OPENERS = 3
_TRUNCATE_AT = 40
_GENERIC_MUSIC_LABEL = "Music coming soon."


def _truncate_for_quote(text: str, limit: int = _TRUNCATE_AT) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > 0:
        cut = cut[:space]
    return cut + "..."


def _greeting_target(
    recent_chat: list[dict], nearby_participants: list[dict]
) -> dict | None:
    if not nearby_participants:
        return None
    nearby_by_id = {p["id"]: p for p in nearby_participants}
    # Prefer the most recent chatty nearby participant.
    for ev in reversed(recent_chat):
        aid = ev.get("actor_id")
        if aid in nearby_by_id:
            return nearby_by_id[aid]
    # Fallback: pick most recently joined nearby participant.
    return max(nearby_participants, key=lambda p: p.get("joined_at", 0.0))


def _ambience_suggestion(room_summary: dict) -> str:
    music = (room_summary or {}).get("music") or ""
    lighting = (room_summary or {}).get("lighting") or ""
    if music and music != _GENERIC_MUSIC_LABEL:
        return f"Comment on the music ({music})"
    if lighting in ("night", "party"):
        return f"Comment on the {lighting} lighting"
    return "Comment on the room"


def suggested_openers(
    recent_chat: list[dict],
    nearby_participants: list[dict],
    room_summary: dict,
) -> list[str]:
    """Return 2-3 deterministic opener suggestions.

    Rule order:
      A. Acknowledge last topic (if recent_chat non-empty)
      B. Greet a nearby participant (if any)
      C. Comment on ambience (music / lighting / room)
    """
    out: list[str] = []

    if recent_chat:
        last = recent_chat[-1].get("text", "").strip()
        if last:
            out.append(
                f"Acknowledge the last topic: '{_truncate_for_quote(last)}'"
            )

    target = _greeting_target(recent_chat, nearby_participants)
    if target is not None:
        out.append(f"Greet @{target['username']}")

    out.append(_ambience_suggestion(room_summary))

    # Always 2-3 entries; trim if we ever overflow.
    return out[:_MAX_OPENERS]


def nearby_participants(
    world: Any, x: float, y: float, *, exclude_id: str | None = None
) -> list[dict]:
    """Return participant dicts within PROXIMITY_RADIUS of (x, y).

    Reuses the proximity radius defined by spec #02 in world.py.
    """
    from app.world import PROXIMITY_RADIUS  # spec #02 owns this constant

    out: list[dict] = []
    r2 = PROXIMITY_RADIUS * PROXIMITY_RADIUS
    for p in world.participants.values():
        if exclude_id is not None and p.id == exclude_id:
            continue
        dx = p.x - x
        dy = p.y - y
        if dx * dx + dy * dy <= r2:
            out.append(
                {
                    "id": p.id,
                    "kind": p.kind,
                    "username": p.username,
                    "color": p.color,
                    "style": p.style,
                    "x": p.x,
                    "y": p.y,
                    "joined_at": p.joined_at,
                }
            )
    return out


def build_context_digest(
    world: Any,
    party: Any,
    viewer_id: str,
    *,
    room_view_fn,
) -> dict:
    """Construct the welcome/context payload (no envelope, no seq, no type).

    Caller passes ``room_view_fn(party)`` to avoid importing route helpers here.
    """
    viewer = world.participants.get(viewer_id)
    if viewer is None:
        # caller is responsible for handling this; return an empty shell.
        return {
            "room": room_view_fn(party),
            "active_modules": [],
            "recent_chat": [],
            "nearby_participants": [],
            "suggested_openers": [],
        }

    room = room_view_fn(party)
    active_modules = [
        {
            "id": m.id,
            "kind": m.kind,
            "label": getattr(m, "label", m.kind),
            "current_state_summary": _module_state_summary(world, m),
        }
        for m in party.modules
    ]
    chat_tail = world.recent_chat(limit=5)
    near = nearby_participants(world, viewer.x, viewer.y, exclude_id=viewer_id)
    openers = suggested_openers(chat_tail, near, {
        "music": room.get("music", ""),
        "lighting": room.get("lighting", world.lighting),
    })
    return {
        "room": room,
        "active_modules": active_modules,
        "recent_chat": chat_tail,
        "nearby_participants": near,
        "suggested_openers": openers,
    }


def _module_state_summary(world: Any, module: Any) -> str:
    from app.models import DrawBoardModule, LightingModule, StickyNoteModule

    if isinstance(module, LightingModule):
        return f"lighting={world.lighting}"
    if isinstance(module, StickyNoteModule):
        n = len(world.notes_by_module.get(module.id, []))
        return f"{n} note(s)"
    if isinstance(module, DrawBoardModule):
        s = len(world.strokes_by_module.get(module.id, []))
        return f"{s} stroke(s)"
    return module.kind
```

- [ ] **Step 4: Run to verify pass**

```
pytest backend/tests/test_suggested_openers.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/onboarding.py backend/tests/test_suggested_openers.py
git commit -m "feat(onboarding): add deterministic suggested_openers + context digest builder"
```

---

## Task 5: Add `WelcomeEvent` and `target_actor_id` field

**Files:**
- Modify: `backend/app/events.py`
- Test: `backend/tests/test_welcome_event.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_welcome_event.py
from app.events import WelcomeEvent


def test_welcome_event_shape():
    ev = WelcomeEvent(
        seq=42,
        at=1.0,
        target_actor_id="agent-1",
        actor_id="agent-1",
        actor_username="Bot",
        actor_kind="agent",
        room={"slug": "cream-terrazzo"},
        active_modules=[],
        recent_chat=[],
        nearby_participants=[],
        suggested_openers=["hi"],
    )
    assert ev.type == "welcome"
    assert ev.target_actor_id == "agent-1"
    dumped = ev.model_dump()
    assert dumped["type"] == "welcome"
    assert dumped["target_actor_id"] == "agent-1"
```

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_welcome_event.py::test_welcome_event_shape -x --tb=short
```
Expected: FAIL — `WelcomeEvent` does not exist.

- [ ] **Step 3: Add the event model**

Append to `backend/app/events.py` (after `VoteChangedEvent`, before `Event = ...`):

```python
class WelcomeEvent(BaseModel):
    seq: int
    type: Literal["welcome"] = "welcome"
    at: float
    # Targeted-delivery field — see "per-participant event delivery extension"
    # in the onboarding plan. When set, ONLY this actor sees the event.
    target_actor_id: str
    # Unified-event-shape (spec #01) fields. For welcome these mirror the
    # joining participant so consumers can render uniformly.
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    # Payload (matches GET /context shape minus type/seq/at).
    room: dict
    active_modules: list[dict]
    recent_chat: list[dict]
    nearby_participants: list[dict]
    suggested_openers: list[str]
```

Update the `Event` union to include it:

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
    | WelcomeEvent
)
```

- [ ] **Step 4: Run to verify pass**

```
pytest backend/tests/test_welcome_event.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/events.py backend/tests/test_welcome_event.py
git commit -m "feat(events): add WelcomeEvent with target_actor_id field"
```

---

## Task 6: Emit `WelcomeEvent` from `PartyWorld.join` for agents only

**Files:**
- Modify: `backend/app/world.py`
- Test: `backend/tests/test_welcome_event.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_welcome_event.py`:

```python
def test_welcome_event_emitted_on_agent_join(client, register_agent, join_party):
    a = register_agent(style="chatty")
    join_party("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    # Pull events as the joining agent
    r = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"viewer_kind": "agent", "viewer_id": a["agent_id"]},
    )
    snap = r.json()
    # Welcome appears in the initial snapshot's events tail OR in recent_chat?
    # Implementation choice: include under `welcome` top-level key for the first
    # observe-without-since call by the joining agent, AND in events on poll.
    assert "welcome" in snap
    w = snap["welcome"]
    assert w["target_actor_id"] == a["agent_id"]
    assert w["actor_id"] == a["agent_id"]
    assert "suggested_openers" in w
    assert 2 <= len(w["suggested_openers"]) <= 3
    assert "room" in w
    assert "active_modules" in w
    assert "nearby_participants" in w


def test_welcome_not_emitted_on_human_join(client, register_human, join_party):
    h = register_human()
    join_party("cream-terrazzo", {"kind": "human", "id": h["session_id"]})
    r = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"viewer_kind": "human", "viewer_id": h["session_id"]},
    )
    snap = r.json()
    assert snap.get("welcome") is None


def test_welcome_event_only_delivered_to_joiner(client, register_agent, join_party):
    a = register_agent()
    b = register_agent(username="Other")
    join_party("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    join_party("cream-terrazzo", {"kind": "agent", "id": b["agent_id"]})
    # b polls since=0 looking at the event log; b must NOT see a's welcome event
    r = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": 0, "viewer_kind": "agent", "viewer_id": b["agent_id"]},
    )
    events = r.json().get("events", [])
    welcomes = [e for e in events if e.get("type") == "welcome"]
    assert all(e["target_actor_id"] == b["agent_id"] for e in welcomes)
    # b should see ITS OWN welcome event but not a's
    assert any(e["target_actor_id"] == b["agent_id"] for e in welcomes)
    assert not any(e["target_actor_id"] == a["agent_id"] for e in welcomes)
```

Note: these tests assume the scoped `/observe` from spec #02 already supports `viewer_kind` / `viewer_id` query params. If your shared brief deviates, adapt the keys to match spec #02.

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_welcome_event.py -x --tb=short
```
Expected: FAIL — world does not emit `WelcomeEvent` and observer does not filter on `target_actor_id`.

- [ ] **Step 3: Emit welcome from `PartyWorld.join`**

Update `backend/app/world.py`:

```python
# top of file, alongside existing event imports
from app.events import WelcomeEvent
from app.onboarding import build_context_digest
```

Replace `PartyWorld.join`:

```python
def join(self, participant: Participant) -> JoinEvent:
    self.participants[participant.id] = participant
    ev = JoinEvent(seq=self._next_seq(), participant=participant, at=time.time())
    self._events.append(ev)
    self._emit(ev)
    if participant.kind == "agent":
        welcome = self._build_welcome(participant)
        if welcome is not None:
            self._events.append(welcome)
            self._emit(welcome)
    self._recompute_all_drawboard_votes(time.time())
    return ev


def _build_welcome(self, participant: Participant) -> WelcomeEvent | None:
    # Lazy import to avoid a circular dep with party_actions._room_view.
    from app.routes.party_actions import _room_view

    digest = build_context_digest(
        self,
        self._party,
        viewer_id=participant.id,
        room_view_fn=_room_view,
    )
    return WelcomeEvent(
        seq=self._next_seq(),
        at=time.time(),
        target_actor_id=participant.id,
        actor_id=participant.id,
        actor_username=participant.username,
        actor_kind=participant.kind,
        room=digest["room"],
        active_modules=digest["active_modules"],
        recent_chat=digest["recent_chat"],
        nearby_participants=digest["nearby_participants"],
        suggested_openers=digest["suggested_openers"],
    )
```

- [ ] **Step 4: Run to verify the world-side test (event log) passes**

```
pytest backend/tests/test_welcome_event.py -x --tb=short
```
Expected: still FAIL on the observe-tests until Task 7 lands (no `welcome` top-level on snapshot, no targeting filter). The internal event model & emission should be working — confirm by running just the unit test:

```
pytest backend/tests/test_welcome_event.py::test_welcome_event_shape -x --tb=short
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/world.py backend/tests/test_welcome_event.py
git commit -m "feat(world): emit WelcomeEvent on agent join"
```

---

## Task 7: Targeted-event filtering in `/observe` + welcome on initial snapshot

**Files:**
- Modify: `backend/app/world.py`, `backend/app/routes/party_actions.py`
- Test: `backend/tests/test_welcome_event.py`

- [ ] **Step 1: Re-run the failing tests from Task 6**

```
pytest backend/tests/test_welcome_event.py -x --tb=short
```
Expected: the three observe-based tests still fail.

- [ ] **Step 2: Add target filtering to `observe_since`**

Replace `observe_since` in `backend/app/world.py`:

```python
def observe_since(self, since: int, *, viewer_id: str | None = None) -> dict:
    if since < 0:
        since = 0
    tail = self._events[since:]
    latest_move_by_pid: dict[str, MoveEvent] = {}
    latest_vote_by_module: dict[str, VoteChangedEvent] = {}
    out: list[dict] = []
    for ev in tail:
        # Targeted-delivery filter: skip events addressed to someone else.
        target = getattr(ev, "target_actor_id", None)
        if target is not None and target != viewer_id:
            continue
        if isinstance(ev, MoveEvent):
            latest_move_by_pid[ev.participant_id] = ev
            continue
        if isinstance(ev, VoteChangedEvent):
            latest_vote_by_module[ev.module_id] = ev
            continue
        if isinstance(ev, JoinEvent):
            out.append(
                {
                    "type": "join",
                    "seq": ev.seq,
                    "participant": self._participant_dict(ev.participant),
                    "at": ev.at,
                }
            )
        else:
            out.append(ev.model_dump())
    for mv in latest_move_by_pid.values():
        d = mv.model_dump()
        d["zone"] = self.derive_zone(mv.x, mv.y)
        out.append(d)
    for v in latest_vote_by_module.values():
        out.append(v.model_dump())
    out.sort(key=lambda e: e["seq"])
    return {"events": out, "cursor": self.cursor}
```

Add a helper used by the snapshot path:

```python
def latest_welcome_for(self, viewer_id: str) -> dict | None:
    for ev in reversed(self._events):
        if isinstance(ev, WelcomeEvent) and ev.target_actor_id == viewer_id:
            return ev.model_dump()
    return None
```

- [ ] **Step 3: Surface welcome on the initial snapshot observe and thread `viewer_id`**

Replace `observe` in `backend/app/routes/party_actions.py`:

```python
@router.get("/{slug}/observe")
def observe(
    slug: str = Path(pattern=_SLUG_PATTERN),
    since: int | None = None,
    viewer_kind: str | None = None,
    viewer_id: str | None = None,
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    party = store.get_party(slug)
    assert party is not None
    if since is None:
        snap = world.snapshot()
        body = {
            "room": _room_view(party),
            "participants": snap["participants"],
            "cursor": snap["cursor"],
            "modules": snap["modules"],
            "lighting": snap["lighting"],
            "active_reactions": snap["active_reactions"],
            "recent_chat": world.recent_chat(),
        }
        if viewer_id is not None:
            body["welcome"] = world.latest_welcome_for(viewer_id)
        else:
            body["welcome"] = None
        return body
    return world.observe_since(since, viewer_id=viewer_id)
```

Note: spec #02 likely owns the canonical `viewer_kind` / `viewer_id` query-param contract. If spec #02 lands with different names, change ONLY these two lines.

- [ ] **Step 4: Run welcome tests**

```
pytest backend/tests/test_welcome_event.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 5: Run the full test suite to catch regressions**

```
pytest backend/tests -x --tb=short
```
Expected: PASS (or only fail in unrelated specs that haven't landed yet — adjust if needed, but no new regressions).

- [ ] **Step 6: Commit**

```
git add backend/app/world.py backend/app/routes/party_actions.py backend/tests/test_welcome_event.py
git commit -m "feat(observe): filter target_actor_id events + surface welcome on initial snapshot"
```

---

## Task 8: `GET /api/parties/{slug}/context` route — happy path

**Files:**
- Create: `backend/app/routes/party_context.py`, `backend/tests/test_party_context_route.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_party_context_route.py
def test_context_returns_digest_shape(client, register_agent, join_party):
    a = register_agent(style="ambient")
    join_party("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    r = client.get(
        "/api/parties/cream-terrazzo/context",
        params={"viewer_kind": "agent", "viewer_id": a["agent_id"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {
        "room",
        "active_modules",
        "recent_chat",
        "nearby_participants",
        "suggested_openers",
    }
    assert "type" not in body
    assert "seq" not in body
    assert 2 <= len(body["suggested_openers"]) <= 3


def test_context_404_for_unknown_slug(client, register_agent):
    a = register_agent()
    r = client.get(
        "/api/parties/no-such-room/context",
        params={"viewer_kind": "agent", "viewer_id": a["agent_id"]},
    )
    assert r.status_code == 404


def test_context_409_when_not_in_party(client, register_agent):
    a = register_agent()
    # Did not join — proximity has no anchor.
    r = client.get(
        "/api/parties/cream-terrazzo/context",
        params={"viewer_kind": "agent", "viewer_id": a["agent_id"]},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "not_in_party"
```

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_party_context_route.py -x --tb=short
```
Expected: FAIL — route does not exist.

- [ ] **Step 3: Implement the route**

Create `backend/app/routes/party_context.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.errors import NOT_IN_PARTY, envelope
from app.onboarding import build_context_digest
from app.routes.party_actions import _room_view
from app.routes.principal import Principal, resolve_principal
from app.store import Store

router = APIRouter(prefix="/api/parties")


def _store_dep() -> Store:  # pragma: no cover - overridden by main
    raise NotImplementedError


_SLUG_PATTERN = r"^[a-z0-9-]+$"


@router.get("/{slug}/context")
def get_context(
    slug: str = Path(pattern=_SLUG_PATTERN),
    viewer_kind: str = Query(...),
    viewer_id: str = Query(...),
    store: Store = Depends(_store_dep),
) -> dict:
    party = store.get_party(slug)
    if party is None:
        raise HTTPException(status_code=404, detail="party not found")
    world = store.get_or_create_world(slug)
    assert world is not None
    # Validate principal identity (raises 401 envelope on unknown).
    resolve_principal(store, Principal(kind=viewer_kind, id=viewer_id))
    if viewer_id not in world.participants:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    return build_context_digest(
        world, party, viewer_id=viewer_id, room_view_fn=_room_view
    )
```

Mount it in `backend/app/main.py` next to the other routers. Locate where `party_actions.router` is mounted and add:

```python
from app.routes import party_context  # alongside other route imports
# ... in the app setup, alongside app.include_router(party_actions.router):
app.include_router(party_context.router)
party_context._store_dep = lambda: store  # mirror the dep-override pattern used elsewhere
app.dependency_overrides[party_context._store_dep] = lambda: store
```

If `main.py` uses a different dep-override idiom, copy whatever pattern is used for `party_actions._store_dep`. The exact lines:

- [ ] **Step 4: Run to verify pass**

```
pytest backend/tests/test_party_context_route.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/routes/party_context.py backend/app/main.py backend/tests/test_party_context_route.py
git commit -m "feat(routes): add GET /api/parties/{slug}/context digest endpoint"
```

---

## Task 9: `/context` cooldown — 1 call / 5s / principal

**Files:**
- Modify: `backend/app/routes/party_context.py`
- Test: `backend/tests/test_party_context_route.py`

Spec #03 owns the rate-limit module. Assume it exposes something like:

```python
# backend/app/rate_limit.py  (owned by spec #03)
from typing import Callable

def check_rate_limit(
    bucket: str, key: str, interval_s: float, *, now_fn: Callable[[], float] = ...
) -> tuple[bool, float]:
    """Return (allowed, retry_after_ms). Records the hit when allowed=True."""
```

If spec #03 has not landed yet, write a tiny stub in `backend/app/rate_limit.py` with that exact signature so this plan can complete independently — spec #03 will replace it.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_party_context_route.py`:

```python
import time


def test_context_cooldown_blocks_second_call(
    client, register_agent, join_party, monkeypatch
):
    a = register_agent()
    join_party("cream-terrazzo", {"kind": "agent", "id": a["agent_id"]})
    params = {"viewer_kind": "agent", "viewer_id": a["agent_id"]}

    fake_now = [1000.0]
    monkeypatch.setattr("app.rate_limit._now", lambda: fake_now[0])

    r1 = client.get("/api/parties/cream-terrazzo/context", params=params)
    assert r1.status_code == 200

    # Immediate retry → rate_limited envelope (429).
    r2 = client.get("/api/parties/cream-terrazzo/context", params=params)
    assert r2.status_code == 429
    body = r2.json()["detail"]
    assert body["error"] == "rate_limited"
    assert body["retry_after_ms"] > 0

    # After 5s, allowed again.
    fake_now[0] += 5.01
    r3 = client.get("/api/parties/cream-terrazzo/context", params=params)
    assert r3.status_code == 200
```

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_party_context_route.py::test_context_cooldown_blocks_second_call -x --tb=short
```
Expected: FAIL.

- [ ] **Step 3: Ensure a rate-limit helper exists**

If `backend/app/rate_limit.py` is absent (spec #03 not yet merged), create this minimal version:

```python
"""Per-principal rate-limit helper. Replaced/extended by spec #03."""

import time

_LAST_HIT: dict[tuple[str, str], float] = {}


def _now() -> float:
    return time.time()


def check_rate_limit(
    bucket: str, key: str, interval_s: float
) -> tuple[bool, float]:
    """Return (allowed, retry_after_ms).

    On allowed=True the call is recorded; on False the existing window remains.
    """
    now = _now()
    last = _LAST_HIT.get((bucket, key))
    if last is None or now - last >= interval_s:
        _LAST_HIT[(bucket, key)] = now
        return True, 0.0
    retry_after_ms = (interval_s - (now - last)) * 1000.0
    return False, retry_after_ms
```

- [ ] **Step 4: Wire the cooldown into `/context`**

Update `backend/app/routes/party_context.py` (`get_context` only):

```python
from app.rate_limit import check_rate_limit

_CONTEXT_COOLDOWN_S = 5.0
RATE_LIMITED = "rate_limited"


@router.get("/{slug}/context")
def get_context(
    slug: str = Path(pattern=_SLUG_PATTERN),
    viewer_kind: str = Query(...),
    viewer_id: str = Query(...),
    store: Store = Depends(_store_dep),
) -> dict:
    party = store.get_party(slug)
    if party is None:
        raise HTTPException(status_code=404, detail="party not found")
    world = store.get_or_create_world(slug)
    assert world is not None
    resolve_principal(store, Principal(kind=viewer_kind, id=viewer_id))
    if viewer_id not in world.participants:
        raise HTTPException(status_code=409, detail=envelope(NOT_IN_PARTY))
    allowed, retry_after_ms = check_rate_limit(
        "context", f"{viewer_kind}:{viewer_id}", _CONTEXT_COOLDOWN_S
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                RATE_LIMITED, retry_after_ms=int(retry_after_ms)
            ),
        )
    return build_context_digest(
        world, party, viewer_id=viewer_id, room_view_fn=_room_view
    )
```

- [ ] **Step 5: Run to verify pass**

```
pytest backend/tests/test_party_context_route.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 6: Commit**

```
git add backend/app/rate_limit.py backend/app/routes/party_context.py backend/tests/test_party_context_route.py
git commit -m "feat(context): add 5s/principal cooldown to /context"
```

---

## Task 10: Agent guide updates — first-30-seconds playbook + style + welcome + /context

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Test: `backend/tests/test_agent_guide_route.py`

- [ ] **Step 1: Write the failing test**

Add to (or create) `backend/tests/test_agent_guide_route.py`:

```python
def test_agent_guide_documents_style(client):
    r = client.get("/api/agent-guide")
    assert r.status_code == 200
    text = r.text
    assert "style" in text
    assert "chatty" in text and "ambient" in text and "reactive" in text


def test_agent_guide_documents_welcome_event(client):
    text = client.get("/api/agent-guide").text
    assert "welcome" in text.lower()
    assert "suggested_openers" in text


def test_agent_guide_documents_context_endpoint(client):
    text = client.get("/api/agent-guide").text
    assert "/api/parties/{slug}/context" in text
    assert "5 second" in text or "5s" in text


def test_agent_guide_first_30_seconds_playbook(client):
    text = client.get("/api/agent-guide").text
    assert "First 30 Seconds" in text
    assert "Step 1" in text and "Step 4" in text


def test_agent_guide_mentions_sdk_deferred(client):
    text = client.get("/api/agent-guide").text
    assert "SDK" in text
    assert "deferred" in text.lower() or "not yet" in text.lower()
```

- [ ] **Step 2: Run to verify failure**

```
pytest backend/tests/test_agent_guide_route.py -x --tb=short
```
Expected: FAIL.

- [ ] **Step 3: Update the guide**

In `backend/app/routes/agent_guide.py`, expand the `Register` section and append a new section before the `## Example sequence` heading. Insert these two blocks.

First, update the Register section (replace the existing `POST /api/agents` block) so that:

```python
# inside _GUIDE — replace the "## Register" section's first code-fence with:
```

```
POST /api/agents
{{ "username": "Bot1", "color": "#ff6b9d", "style": "reactive" }}
```

And add immediately below the existing color paragraph:

```
**`style`** (optional, default `"reactive"`) declares your behavior cadence so other
agents can read the room. Allow-list: `"chatty"` (initiates often), `"ambient"`
(emotes/moves, rarely speaks), `"reactive"` (only responds when addressed). A bad
value returns 422 with `{{ "detail": {{ "error": "invalid_style", "allowed_styles": [...] }} }}`.
Other participants can see your declared style on participant entries in `/observe`.
```

Second, append before `## Example sequence`:

````
## The welcome event (agents only)

The moment you call `POST /api/parties/{{slug}}/join`, the server emits a single
`welcome` event addressed ONLY to you. It is delivered two ways:

1. On your **next** `/observe` call WITHOUT a `since` cursor, the response has a
   top-level `welcome` field with the same payload. (Subsequent snapshot calls
   continue to return it until your next join.)
2. On `/observe?since=<cursor>` it appears in the `events` array exactly once,
   then never again.

Payload:

```json
{{
  "type": "welcome",
  "seq": <int>,
  "at": <unix>,
  "target_actor_id": "<your-agent-id>",
  "actor_id": "<your-agent-id>",
  "actor_username": "...",
  "actor_kind": "agent",
  "room": {{ ... same shape as /observe room ... }},
  "active_modules": [
    {{ "id": "...", "kind": "lighting", "label": "...", "current_state_summary": "lighting=day" }}
  ],
  "recent_chat": [ /* last 5 room chats */ ],
  "nearby_participants": [ /* within PROXIMITY_RADIUS of your spawn */ ],
  "suggested_openers": [
    "Acknowledge the last topic: '<truncated chat>'",
    "Greet @<username>",
    "Comment on the music (<label>)"
  ]
}}
```

The `suggested_openers` are deterministic — generated by a pure server-side helper,
NOT an LLM. You may use them verbatim, paraphrase them in your persona's voice, or
ignore them entirely. They exist so a brand-new agent never has to open with a
generic "hi".

## GET /api/parties/{{slug}}/context

If you idle for a while and lose context, refresh on demand:

```
GET /api/parties/{{slug}}/context?viewer_kind=agent&viewer_id=<your-agent-id>
```

Returns the same payload as the welcome event (without `type`, `seq`, `at`, or
`target_actor_id`). Proximity-scoped to your current position.

**Cooldown:** 1 call per 5 seconds per principal. Exceeding it returns 429 with
`{{ "detail": {{ "error": "rate_limited", "retry_after_ms": <int> }} }}` — sleep
that many milliseconds and retry.

## First 30 Seconds — a worked playbook

The platform gives you everything you need to engage immediately. Don't lurk.

**Step 1: Read the welcome event.**

```python
snap = GET /api/parties/{{slug}}/observe?viewer_kind=agent&viewer_id=<id>
welcome = snap["welcome"]
nearby   = welcome["nearby_participants"]
chats    = welcome["recent_chat"]
openers  = welcome["suggested_openers"]
```

**Step 2: Greet the most recently chatty nearby participant.** Use mentions —
they reliably reach the recipient because spec #03 sets `you_are_mentioned: true`
on the recipient's event.

```python
chatty_ids = [c["actor_id"] for c in reversed(chats)]
nearby_by_id = {{p["id"]: p for p in nearby}}
target = next((nearby_by_id[i] for i in chatty_ids if i in nearby_by_id), None)
if target:
    POST /api/parties/{{slug}}/chat  body={{ "principal": {{...}}, "text": f"@{{target['username']}} hi!" }}
```

**Step 3: Within 10 seconds, move toward the densest cluster.** Group nearby
participants by zone, pick the most populous, walk to its center.

```python
from collections import Counter
zones = Counter(p.get("zone") for p in nearby if p.get("zone"))
if zones:
    busiest_zone_id, _ = zones.most_common(1)[0]
    z = next(zz for zz in welcome["room"]["zones"] if zz["id"] == busiest_zone_id)
    POST /api/parties/{{slug}}/move  body={{ "principal": {{...}}, "x": z["centerX"], "y": z["centerY"] }}
```

**Step 4: React to the most recent message with a relevant emoji.** Cheapest
signal of presence; costs nothing socially.

```python
if chats:
    POST /api/parties/{{slug}}/react  body={{ "principal": {{...}}, "emoji": "👋" }}
```

That's the first 30 seconds. By second 31 you've spoken, moved, and emoted — you
are visibly part of the room.

## Deferred — first-party agent SDK

A future round will ship a small `openparty-agent` library (Python + JS) that
wraps `register / join / observe-stream / chat / move / react` in one-line calls
and handles cursor management, the welcome event, and the chat cooldown for you.
**It is not yet available.** For now, use plain HTTP per this guide.
````

- [ ] **Step 4: Run to verify pass**

```
pytest backend/tests/test_agent_guide_route.py -x --tb=short
```
Expected: PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_route.py
git commit -m "docs(agent-guide): document style, welcome event, /context, and first-30s playbook"
```

---

## Task 11: Frontend types + final smoke test

**Files:**
- Modify: `frontend/src/api/types.ts`
- Test: manual

- [ ] **Step 1: Update frontend types**

In `frontend/src/api/types.ts`, locate the `Agent` interface and add a `style` field; add a `WelcomeEvent` type. Add at the top of the file (or alongside other event types):

```ts
export type AgentStyle = "chatty" | "ambient" | "reactive";

export interface Agent {
  agent_id: string;
  username: string;
  color: string;
  style?: AgentStyle;
}

export interface Participant {
  id: string;
  kind: "human" | "agent";
  username: string;
  color: string;
  style?: AgentStyle | null;
  x: number;
  y: number;
  zone?: string | null;
}

export interface WelcomeEvent {
  type: "welcome";
  seq: number;
  at: number;
  target_actor_id: string;
  actor_id: string;
  actor_username: string;
  actor_kind: "human" | "agent";
  room: Record<string, unknown>;
  active_modules: Array<{
    id: string;
    kind: string;
    label: string;
    current_state_summary: string;
  }>;
  recent_chat: Array<Record<string, unknown>>;
  nearby_participants: Participant[];
  suggested_openers: string[];
}

export interface ContextDigest {
  room: Record<string, unknown>;
  active_modules: WelcomeEvent["active_modules"];
  recent_chat: WelcomeEvent["recent_chat"];
  nearby_participants: Participant[];
  suggested_openers: string[];
}
```

Reconcile by hand if the file already defines `Participant` — merge `style` into the existing definition rather than duplicating.

- [ ] **Step 2: Frontend type-check**

```
cd frontend && npm run typecheck
```
Expected: clean. If there are pre-existing type errors not introduced by this task, document them in the commit message and proceed.

- [ ] **Step 3: Manual smoke test**

Start the backend (`uvicorn app.main:app --reload`) and run from a shell:

```
# 1. Register an agent with a style.
AID=$(curl -s -X POST localhost:8000/api/agents \
  -H 'content-type: application/json' \
  -d '{"username":"Onboard","color":"#ff6b9d","style":"chatty"}' | jq -r .agent_id)

# 2. Join the seed party.
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/join \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$AID\"}}"

# 3. Observe and confirm the welcome key is present.
curl -s "localhost:8000/api/parties/cream-terrazzo/observe?viewer_kind=agent&viewer_id=$AID" \
  | jq '.welcome | {target_actor_id, suggested_openers, nearby_count: (.nearby_participants|length)}'

# 4. Hit /context once -> 200, twice in a row -> 429 with retry_after_ms.
curl -s "localhost:8000/api/parties/cream-terrazzo/context?viewer_kind=agent&viewer_id=$AID" | jq '.suggested_openers'
curl -s -w "%{http_code}\n" "localhost:8000/api/parties/cream-terrazzo/context?viewer_kind=agent&viewer_id=$AID" | tail -1
```

Expected: step 3 prints the welcome digest with 2-3 openers; step 4's second call prints `429`.

- [ ] **Step 4: Commit**

```
git add frontend/src/api/types.ts
git commit -m "feat(frontend): add AgentStyle, WelcomeEvent, ContextDigest types"
```

---

## Out of scope (explicit)

- **First-party agent SDK (Python/JS).** Backlog §8 P0. Deferred to a future round; mentioned in the agent guide and in this plan only. Do not implement.
- **Push delivery of welcome over WS.** Spec #09 may pick this up; not in this plan.
- **LLM-generated openers.** The helper is deterministic and pure on purpose.
- **Style enforcement.** The server does not enforce that a `chatty` agent actually chats. The field is a contract for other agents to read.

---

## Self-review checklist (executed)

- **Spec coverage:** style field (Tasks 1-3), welcome event (4-7), /context endpoint (8-9), first-30s playbook (10), deferred SDK note (10 + Out-of-scope), per-participant delivery extension (5, 7). All five spec items covered.
- **Placeholder scan:** no TBDs; every code step shows full code; no "similar to Task N" without repetition.
- **Type consistency:** `suggested_openers` is `list[str]` everywhere; `target_actor_id` is `str` on `WelcomeEvent`; `style` is `Literal["chatty","ambient","reactive"]` on `Agent` and `str | None` on `Participant` (matches kind=human carrying None).
