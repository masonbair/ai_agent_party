# Discovery & Lobby Implementation Plan (Spec #08)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface live occupancy on the party list, add a public `/preview` peek endpoint (recent room-wide chat + occupancy + room-wide module state), and let lobby visitors peek before joining.

**Architecture:** Backend computes occupancy from `PartyWorld.participants` (humans / agents / active-in-last-5-min by inspecting recent `MoveEvent` / `ChatEvent` / `ReactionEvent` timestamps). A new public route `GET /api/parties/{slug}/preview` returns occupancy + last 5 room-wide chats + lighting + music — **no participant list, no notes, no strokes, no DMs, no proximity chats**. The lobby page adds a small occupancy line on each card and a "Peek" button that opens a modal previewing the room.

**Tech Stack:** FastAPI + Pydantic (backend), React + Vitest + React Testing Library (frontend).

---

## Spec → Task map

| Spec requirement | Task |
|---|---|
| `GET /api/parties` returns `occupancy` on each entry | Task 2, 3 |
| `active_last_5min` counting | Task 2 |
| `GET /api/parties/{slug}/preview` (public, no auth) | Task 5, 6, 7 |
| Preview returns last 5 room-wide chats (no proximity scoping leak) | Task 6 |
| Preview returns lighting + music | Task 7 |
| Preview excludes participants / notes / strokes / DMs | Task 5, 6 |
| Lobby UI shows occupancy line per card | Task 9 |
| Lobby "Peek" button + modal | Task 10, 11 |
| Agent guide mentions occupancy + preview | Task 12 |
| `frontend/src/api/types.ts` updated | Task 8 |

---

## File structure

**Create**
- `backend/app/occupancy.py` — pure helper that computes the `occupancy` dict from a `PartyWorld`.
- `backend/tests/test_occupancy.py` — unit tests for the helper.
- `backend/tests/test_parties_occupancy.py` — route-level tests for `GET /api/parties` occupancy.
- `backend/tests/test_party_preview_route.py` — route tests for `GET /api/parties/{slug}/preview`.
- `frontend/src/components/PartyPeekModal.tsx` — modal that shows the preview payload.
- `frontend/tests/PartyPeekModal.test.tsx` — modal tests.

**Modify**
- `backend/app/models.py` — add `Occupancy`, `PartyListEntry`, `PartyPreviewResponse` Pydantic models.
- `backend/app/routes/parties.py` — extend `list_parties`; add `preview_party`.
- `backend/app/store.py` — expose `get_world(slug)` (read-only — does not auto-create).
- `backend/app/routes/agent_guide.py` — mention occupancy + preview.
- `backend/tests/test_agent_guide_content.py` — assert new content.
- `frontend/src/api/types.ts` — add `Occupancy`, `PartyListEntry`, `PartyPreviewResponse`.
- `frontend/src/pages/Lobby.tsx` — occupancy line + Peek button.
- `frontend/tests/Lobby.test.tsx` — assert occupancy text + Peek button opens modal.

**Out of scope**
- Live websocket-driven occupancy refresh — list endpoint is poll-only.
- Showing participant identities in the preview (privacy).
- Including proximity-scoped chats (spec #02 explicitly forbids).
- Walking history beyond the last 5 chats.
- Music feature itself — spec #07 owns the field. This plan uses the `PartyConfig.music` static field already on the model (`{url, label}`) AND, if spec #07 has landed and added `world.music_state`, also includes that. Implementation handles both via `getattr`.

---

## Task 1: Add Pydantic models for occupancy and preview

**Files:**
- Modify: `backend/app/models.py`

- [ ] **Step 1: Add the new models**

Open `backend/app/models.py` and append the following after the existing `PartiesListResponse`:

```python
class Occupancy(BaseModel):
    humans: int
    agents: int
    total: int
    active_last_5min: int


class PartyListEntry(PartyConfig):
    occupancy: Occupancy


class PartiesListResponseV2(BaseModel):
    parties: list[PartyListEntry]


class PartyPreviewMusic(BaseModel):
    url: str | None
    label: str


class PartyPreviewChat(BaseModel):
    seq: int
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    text: str
    at: float


class PartyPreviewResponse(BaseModel):
    slug: str
    name: str
    description: str
    occupancy: Occupancy
    lighting: LightingPreset
    music: PartyPreviewMusic
    recent_chat: list[PartyPreviewChat]
```

Note: `PartyListEntry` inherits from `PartyConfig` so existing clients keep all current fields. We will **replace** `PartiesListResponse` in place rather than introduce a v2 path — clients in this repo are versioned together. Rename `PartiesListResponseV2` → `PartiesListResponse` after deleting the old one. Final state should have one `PartiesListResponse` class whose `parties` is `list[PartyListEntry]`.

- [ ] **Step 2: Replace the old `PartiesListResponse`**

Delete the existing `class PartiesListResponse(BaseModel): parties: list[PartyConfig]` and rename `PartiesListResponseV2` to `PartiesListResponse`. The final block at the bottom of `models.py` should read:

```python
class Occupancy(BaseModel):
    humans: int
    agents: int
    total: int
    active_last_5min: int


class PartyListEntry(PartyConfig):
    occupancy: Occupancy


class PartiesListResponse(BaseModel):
    parties: list[PartyListEntry]


class PartyPreviewMusic(BaseModel):
    url: str | None
    label: str


class PartyPreviewChat(BaseModel):
    seq: int
    actor_id: str
    actor_username: str
    actor_kind: Literal["human", "agent"]
    text: str
    at: float


class PartyPreviewResponse(BaseModel):
    slug: str
    name: str
    description: str
    occupancy: Occupancy
    lighting: LightingPreset
    music: PartyPreviewMusic
    recent_chat: list[PartyPreviewChat]
```

- [ ] **Step 3: Run import sanity check**

Run: `cd backend && python -c "from app.models import Occupancy, PartyListEntry, PartiesListResponse, PartyPreviewResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models.py
git commit -m "feat(parties): add Occupancy + PartyPreview models"
```

---

## Task 2: Occupancy helper — TDD

**Files:**
- Create: `backend/app/occupancy.py`
- Test: `backend/tests/test_occupancy.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_occupancy.py`:

```python
import time

import pytest

from app.events import Agent, ChatEvent, MoveEvent, Participant
from app.models import PartyConfig
from app.occupancy import compute_occupancy
from app.parties_data import PARTY_REGISTRY
from app.world import PartyWorld


def _world() -> PartyWorld:
    party: PartyConfig = list(PARTY_REGISTRY.values())[0]
    return PartyWorld(party, party_slug=party.slug)


def _human(id_: str, x: float = 100.0) -> Participant:
    return Participant(id=id_, kind="human", username=f"h_{id_}", color="#ff6b9d", x=x, y=100.0)


def _agent(id_: str, x: float = 110.0) -> Participant:
    return Participant(id=id_, kind="agent", username=f"a_{id_}", color="#ff6b9d", x=x, y=100.0)


def test_empty_room():
    w = _world()
    occ = compute_occupancy(w, now=time.time())
    assert occ == {"humans": 0, "agents": 0, "total": 0, "active_last_5min": 0}


def test_mixed_population_idle_default():
    # New joiners count toward active (they have a recent join event).
    w = _world()
    w.join(_human("h1"))
    w.join(_agent("a1"))
    w.join(_agent("a2"))
    occ = compute_occupancy(w, now=time.time())
    assert occ == {"humans": 1, "agents": 2, "total": 3, "active_last_5min": 3}


def test_active_last_5min_counts_only_recent_actors():
    w = _world()
    w.join(_human("h1"))
    w.join(_human("h2"))
    # Backdate h2 by writing a stale move directly.
    # h1 will produce a fresh move; h2 stays idle.
    w.move("h1", 120.0, 100.0)
    now = time.time()
    # Rewrite h2's join timestamp into the past so they look idle.
    for ev in w._events:
        if hasattr(ev, "participant") and getattr(ev.participant, "id", None) == "h2":
            object.__setattr__(ev, "at", now - 600.0)
    occ = compute_occupancy(w, now=now)
    assert occ["humans"] == 2
    assert occ["total"] == 2
    assert occ["active_last_5min"] == 1  # only h1 acted in last 5min


def test_active_only_counts_participants_currently_in_room():
    # A participant who left should not count, even with a recent event.
    w = _world()
    w.join(_human("h1"))
    w.join(_human("h2"))
    w.leave("h2")
    occ = compute_occupancy(w, now=time.time())
    assert occ["humans"] == 1
    assert occ["total"] == 1
    assert occ["active_last_5min"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_occupancy.py -v`
Expected: ImportError / ModuleNotFoundError on `app.occupancy`.

- [ ] **Step 3: Implement the helper**

Create `backend/app/occupancy.py`:

```python
"""Compute a public occupancy summary for a PartyWorld.

Used by:
- ``GET /api/parties`` (per-entry ``occupancy``)
- ``GET /api/parties/{slug}/preview`` (top-level ``occupancy``)

"active in the last 5 minutes" is derived from the world's event log: any
participant currently in the room who has produced a ``join``, ``move``,
``chat``, or ``reaction`` event with ``at >= now - 300``. We intentionally
do NOT consult walls / proximity here — this is a coarse room-wide stat.
"""
from __future__ import annotations

from app.events import ChatEvent, JoinEvent, MoveEvent, ReactionEvent
from app.world import PartyWorld

ACTIVE_WINDOW_SECONDS = 300.0


def compute_occupancy(world: PartyWorld, *, now: float) -> dict:
    humans = 0
    agents = 0
    for p in world.participants.values():
        if p.kind == "human":
            humans += 1
        elif p.kind == "agent":
            agents += 1
    total = humans + agents

    if total == 0:
        return {"humans": 0, "agents": 0, "total": 0, "active_last_5min": 0}

    threshold = now - ACTIVE_WINDOW_SECONDS
    present_ids = set(world.participants.keys())
    active: set[str] = set()
    # Walk events newest-first; bail once we cross the threshold.
    for ev in reversed(world.events):
        if ev.at < threshold:
            break
        actor_id: str | None = None
        if isinstance(ev, JoinEvent):
            actor_id = ev.participant.id
        elif isinstance(ev, (MoveEvent, ChatEvent)):
            actor_id = ev.participant_id
        elif isinstance(ev, ReactionEvent):
            actor_id = ev.actor_id
        if actor_id is not None and actor_id in present_ids:
            active.add(actor_id)
        if len(active) == total:
            break

    return {
        "humans": humans,
        "agents": agents,
        "total": total,
        "active_last_5min": len(active),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_occupancy.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/occupancy.py backend/tests/test_occupancy.py
git commit -m "feat(parties): add compute_occupancy helper"
```

---

## Task 3: `GET /api/parties` returns occupancy — TDD

**Files:**
- Test: `backend/tests/test_parties_occupancy.py`
- Modify: `backend/app/routes/parties.py`
- Modify: `backend/app/store.py`

- [ ] **Step 1: Add a read-only `get_world` to the store**

In `backend/app/store.py`, add this method to `Store` (place near `get_or_create_world`):

```python
    def get_world(self, slug: str) -> PartyWorld | None:
        """Return the live world for ``slug`` without instantiating it.

        Used by read-only endpoints (list, preview) so the call doesn't
        materialize an empty world as a side effect of being polled.
        """
        return self._worlds.get(slug)
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_parties_occupancy.py`:

```python
from app.events import Participant


def test_list_parties_includes_occupancy_zero_for_unvisited_party(client):
    res = client.get("/api/parties")
    assert res.status_code == 200
    body = res.json()
    assert "parties" in body and len(body["parties"]) >= 1
    for entry in body["parties"]:
        assert entry["occupancy"] == {
            "humans": 0,
            "agents": 0,
            "total": 0,
            "active_last_5min": 0,
        }


def test_list_parties_counts_mixed_population(client, register_human, register_agent, join_party):
    h = register_human()
    a = register_agent()
    join_party(h, slug="cream-terrazzo")
    join_party(a, slug="cream-terrazzo")
    res = client.get("/api/parties")
    assert res.status_code == 200
    entry = next(p for p in res.json()["parties"] if p["slug"] == "cream-terrazzo")
    occ = entry["occupancy"]
    assert occ["humans"] == 1
    assert occ["agents"] == 1
    assert occ["total"] == 2
    assert occ["active_last_5min"] == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_parties_occupancy.py -v`
Expected: KeyError on `occupancy` or 500 response — the route returns plain `PartyConfig` entries.

- [ ] **Step 4: Update the route**

Replace `list_parties` in `backend/app/routes/parties.py` with:

```python
import time

from app.models import (
    PartiesListResponse,
    PartyConfig,
    PartyListEntry,
    Occupancy,
)
from app.occupancy import compute_occupancy


@router.get("", response_model=PartiesListResponse)
def list_parties(store: Store = Depends(_store_dep)) -> PartiesListResponse:
    now = time.time()
    entries: list[PartyListEntry] = []
    for party in store.list_parties():
        world = store.get_world(party.slug)
        if world is None:
            occ = Occupancy(humans=0, agents=0, total=0, active_last_5min=0)
        else:
            occ = Occupancy(**compute_occupancy(world, now=now))
        entries.append(
            PartyListEntry(**party.model_dump(), occupancy=occ)
        )
    return PartiesListResponse(parties=entries)
```

Keep the existing `import` block intact; add the `time`, `PartyListEntry`, `Occupancy`, and `compute_occupancy` imports at the top of the file.

- [ ] **Step 5: Run all backend tests touched by the model rename**

Run: `cd backend && pytest tests/test_parties_occupancy.py tests/test_agent_flow.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/parties.py backend/app/store.py backend/tests/test_parties_occupancy.py
git commit -m "feat(parties): surface occupancy on GET /api/parties"
```

---

## Task 4: Sweep frontend type breakage

**Files:**
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Add the new types**

In `frontend/src/api/types.ts`, add after the existing `PartyConfig`:

```ts
export type Occupancy = {
  humans: number;
  agents: number;
  total: number;
  active_last_5min: number;
};

export type PartyListEntry = PartyConfig & { occupancy: Occupancy };
```

- [ ] **Step 2: Change `PartiesListResponse` to use the new entry type**

Replace:

```ts
export type PartiesListResponse = {
  parties: PartyConfig[];
};
```

with:

```ts
export type PartiesListResponse = {
  parties: PartyListEntry[];
};
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors. (`Lobby.tsx` already passes `p` typed as `PartyConfig` to `PartyPreview` which only needs `PartyConfig` fields — assignment from `PartyListEntry` is structurally compatible.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/types.ts
git commit -m "feat(types): add Occupancy and PartyListEntry"
```

---

## Task 5: `GET /api/parties/{slug}/preview` — 404 + empty-room shape (TDD)

**Files:**
- Test: `backend/tests/test_party_preview_route.py`
- Modify: `backend/app/routes/parties.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_party_preview_route.py`:

```python
def test_preview_unknown_slug_404(client):
    res = client.get("/api/parties/does-not-exist/preview")
    assert res.status_code == 404
    assert res.json()["detail"]["error"] == "party_not_found"


def test_preview_empty_room_shape(client):
    res = client.get("/api/parties/cream-terrazzo/preview")
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == "cream-terrazzo"
    assert body["name"]
    assert body["description"] is not None
    assert body["occupancy"] == {
        "humans": 0,
        "agents": 0,
        "total": 0,
        "active_last_5min": 0,
    }
    assert body["lighting"] == "day"
    assert "music" in body and set(body["music"].keys()) == {"url", "label"}
    assert body["recent_chat"] == []
    # Privacy guarantees: these keys must NOT appear.
    assert "participants" not in body
    assert "notes" not in body
    assert "strokes" not in body
    assert "dms" not in body
    assert "modules" not in body


def test_preview_does_not_require_auth(client):
    # No session cookie / agent_id header — must still succeed.
    res = client.get("/api/parties/cream-terrazzo/preview")
    assert res.status_code == 200
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend && pytest tests/test_party_preview_route.py -v`
Expected: 404 on every request (route not yet defined).

- [ ] **Step 3: Implement the route**

In `backend/app/routes/parties.py`, add at the top of the imports:

```python
from app.errors import error_detail
from app.models import (
    PartyPreviewChat,
    PartyPreviewMusic,
    PartyPreviewResponse,
)
```

If `app.errors` does not yet expose an `error_detail` helper, inline the dict instead: `detail={"error": "party_not_found", "message": "no party with that slug"}`. Check the existing helpers — spec #01 owns the sweep; use whatever shape it standardized on.

Then add the route below `get_party`:

```python
@router.get("/{slug}/preview", response_model=PartyPreviewResponse)
def preview_party(
    slug: str = Path(pattern=r"^[a-z0-9-]+$"),
    store: Store = Depends(_store_dep),
) -> PartyPreviewResponse:
    party = store.get_party(slug)
    if party is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "party_not_found",
                "message": f"no party with slug {slug!r}",
            },
        )
    world = store.get_world(slug)
    now = time.time()
    if world is None:
        occ = Occupancy(humans=0, agents=0, total=0, active_last_5min=0)
        lighting = "day"
        recent: list[PartyPreviewChat] = []
    else:
        occ = Occupancy(**compute_occupancy(world, now=now))
        lighting = world.lighting
        recent = [
            PartyPreviewChat(
                seq=c["seq"],
                actor_id=c.get("actor_id") or c["participant_id"],
                actor_username=c.get("actor_username", ""),
                actor_kind=c.get("actor_kind", "human"),
                text=c["text"],
                at=c["at"],
            )
            for c in world.recent_chat(limit=5)
        ]
    music = PartyPreviewMusic(url=party.music.url, label=party.music.label)
    return PartyPreviewResponse(
        slug=party.slug,
        name=party.name,
        description=party.description,
        occupancy=occ,
        lighting=lighting,
        music=music,
        recent_chat=recent,
    )
```

Add `time` to imports if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_party_preview_route.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/parties.py backend/tests/test_party_preview_route.py
git commit -m "feat(parties): public /preview endpoint with empty-room shape"
```

---

## Task 6: Preview returns last 5 room-wide chats (TDD)

**Files:**
- Modify: `backend/tests/test_party_preview_route.py`

- [ ] **Step 1: Append a test for recent chats**

Add to `backend/tests/test_party_preview_route.py`:

```python
def test_preview_returns_last_5_chats_room_wide(
    client, register_human, join_party
):
    h = register_human()
    join_party(h, slug="cream-terrazzo")
    # Send 7 chats — preview should expose the last 5 in chronological order.
    for i in range(7):
        r = client.post(
            "/api/parties/cream-terrazzo/chat",
            json={"principal": {"kind": "human", "id": h["session_id"]}, "text": f"msg{i}"},
        )
        assert r.status_code == 200, r.text

    res = client.get("/api/parties/cream-terrazzo/preview")
    assert res.status_code == 200
    chats = res.json()["recent_chat"]
    assert [c["text"] for c in chats] == ["msg2", "msg3", "msg4", "msg5", "msg6"]
    for c in chats:
        assert c["actor_username"] == h["username"]
        assert c["actor_kind"] == "human"
        assert isinstance(c["seq"], int)
        assert isinstance(c["at"], (int, float))
```

If the `/api/parties/{slug}/chat` route uses a different shape in your tree (e.g. requires the chat to flow through `/api/parties/{slug}/actions/chat`), match whatever pattern `backend/tests/test_chat_validation.py` uses. The `client` + `register_human` + `join_party` fixtures in `conftest.py` already encapsulate that — prefer extending whatever fixture posts a chat instead of hand-rolling the request.

- [ ] **Step 2: Run to confirm pass**

Run: `cd backend && pytest tests/test_party_preview_route.py -v`
Expected: 4 passed. If the new test fails because chats are stored with `participant_id` only (no `actor_*` flat fields yet — spec #01 may not have landed), update the preview implementation's fallback to use `participant_id` for both id and username lookup via `world.participants`. The current code already does this for `actor_id`; do the same for `actor_username`:

```python
            actor_username = c.get("actor_username")
            if not actor_username:
                p = world.participants.get(c.get("participant_id"))
                actor_username = p.username if p else ""
```

Slot that into the comprehension as needed.

- [ ] **Step 3: Add a proximity-scoping guard test**

This is the critical privacy test — proves we are NOT bypassing spec #02. Append:

```python
def test_preview_chat_does_not_include_proximity_metadata(
    client, register_human, join_party
):
    h = register_human()
    join_party(h, slug="cream-terrazzo")
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "human", "id": h["session_id"]}, "text": "hi"},
    )
    res = client.get("/api/parties/cream-terrazzo/preview")
    chats = res.json()["recent_chat"]
    assert chats and chats[0]["text"] == "hi"
    forbidden = {"x", "y", "scope", "audience", "audience_ids", "heard_by"}
    leaked = forbidden.intersection(chats[0].keys())
    assert not leaked, f"preview chat leaked proximity-only fields: {leaked}"
```

Run: `cd backend && pytest tests/test_party_preview_route.py -v`
Expected: 5 passed. The `PartyPreviewChat` model already enforces this — the test exists as a regression guard.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_party_preview_route.py
git commit -m "test(preview): assert recent chats + proximity-field guard"
```

---

## Task 7: Preview wires music module state if spec #07 has landed (TDD)

**Files:**
- Modify: `backend/app/routes/parties.py`
- Modify: `backend/tests/test_party_preview_route.py`

- [ ] **Step 1: Write a test that uses the static music field**

Static `PartyConfig.music` is always present. Append:

```python
def test_preview_includes_static_music_metadata(client):
    res = client.get("/api/parties/cream-terrazzo/preview")
    music = res.json()["music"]
    assert "url" in music
    assert "label" in music
```

Run: `cd backend && pytest tests/test_party_preview_route.py::test_preview_includes_static_music_metadata -v`
Expected: passes already (Task 5 implementation already populates `music` from `party.music`).

- [ ] **Step 2: Defensive integration with spec #07**

If spec #07 has merged, `PartyWorld` may expose a `music_state` attribute (e.g. `{playing: bool, track: str, started_at: float}`). Before reading it, guard with `getattr`. Update the route in `backend/app/routes/parties.py` to:

```python
    music_url = party.music.url
    music_label = party.music.label
    if world is not None:
        world_music = getattr(world, "music_state", None)
        if isinstance(world_music, dict):
            music_url = world_music.get("url", music_url)
            music_label = world_music.get("label", music_label)
    music = PartyPreviewMusic(url=music_url, label=music_label)
```

If spec #07 has not landed, this is a no-op. Do not import from any spec-#07 module — keep the integration purely duck-typed.

- [ ] **Step 3: Run the full preview test file**

Run: `cd backend && pytest tests/test_party_preview_route.py -v`
Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/parties.py backend/tests/test_party_preview_route.py
git commit -m "feat(preview): include music state with spec-07 fallback"
```

---

## Task 8: Frontend types — `PartyPreviewResponse`

**Files:**
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Add the type**

Append to `frontend/src/api/types.ts`:

```ts
export type PartyPreviewChat = {
  seq: number;
  actor_id: string;
  actor_username: string;
  actor_kind: 'human' | 'agent';
  text: string;
  at: number;
};

export type PartyPreviewResponse = {
  slug: string;
  name: string;
  description: string;
  occupancy: Occupancy;
  lighting: LightingPreset;
  music: { url: string | null; label: string };
  recent_chat: PartyPreviewChat[];
};
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts
git commit -m "feat(types): add PartyPreviewResponse"
```

---

## Task 9: Lobby — render occupancy line on each card (TDD)

**Files:**
- Modify: `frontend/tests/Lobby.test.tsx`
- Modify: `frontend/src/pages/Lobby.tsx`

- [ ] **Step 1: Extend the test fixture and add a failing test**

In `frontend/tests/Lobby.test.tsx`, update `partiesResponse.parties[0]` to include an `occupancy` block:

```ts
const partiesResponse = {
  parties: [
    {
      slug: 'cream-terrazzo',
      name: 'Cream Terrazzo Lounge',
      description: 'A bright, friendly room.',
      theme: { floor: '#f4ead5', accent: '#ff6b9d' },
      zones: [
        {
          id: 'dance',
          label: 'DANCE',
          x: 6, y: 8, width: 34, height: 36,
          color: '#ff6b9d', labelColor: '#ffffff', borderColor: '#8b1a4a',
        },
      ],
      music: { url: null, label: 'Music coming soon' },
      worldSize: { width: 800, height: 500 },
      room: {
        clipPath: null,
        border: '6px solid #8b6f47',
        borderRadius: 12,
        walls: [{ x: 50, y: 0, width: 0.75, height: 30, color: '#8b6f47' }],
      },
      occupancy: { humans: 2, agents: 3, total: 5, active_last_5min: 4 },
    },
  ],
};
```

Add a new test inside the `describe('Lobby', …)` block:

```tsx
  it('shows the occupancy summary on each card', async () => {
    render(
      <SessionIdProvider>
        <MemoryRouter initialEntries={['/lobby']}>
          <Routes>
            <Route path="/lobby" element={<Lobby />} />
            <Route path="/party/:slug" element={<div>Party page</div>} />
          </Routes>
        </MemoryRouter>
      </SessionIdProvider>,
    );

    expect(
      await screen.findByText(/2 humans · 3 agents · 4 active/i),
    ).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd frontend && npx vitest run tests/Lobby.test.tsx`
Expected: the new test fails — text not found.

- [ ] **Step 3: Update `Lobby.tsx`**

Replace `frontend/src/pages/Lobby.tsx` with:

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';
import type { PartiesListResponse, PartyListEntry } from '../api/types';
import PartyPreview from '../components/PartyPreview';
import PartyPeekModal from '../components/PartyPeekModal';
import { useSession } from '../hooks/useSession';

export default function Lobby() {
  const session = useSession();
  const navigate = useNavigate();
  const [parties, setParties] = useState<PartyListEntry[] | null>(null);
  const [peekSlug, setPeekSlug] = useState<string | null>(null);

  useEffect(() => {
    if (session.status !== 'authed') return;
    apiGet<PartiesListResponse>('/api/parties')
      .then((res) => setParties(res.parties))
      .catch(() => setParties([]));
  }, [session.status]);

  if (session.status !== 'authed') return null;

  return (
    <main
      style={{
        maxWidth: 'min(1100px, 92vw)',
        margin: 'clamp(24px, 6vh, 40px) auto',
        padding: 'clamp(16px, 4vw, 24px)',
      }}
    >
      <h1 style={{ fontSize: 'clamp(22px, 5vw, 32px)', margin: 0 }}>
        Pick a party, {session.user.username}
      </h1>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))',
          gap: 16,
          marginTop: 16,
        }}
      >
        {parties === null && <p>Loading parties…</p>}
        {parties?.map((p) => (
          <div
            key={p.slug}
            style={{
              padding: 12,
              border: `2px solid ${p.theme.accent}`,
              borderRadius: 12,
              background: '#fff',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <button
              type="button"
              onClick={() => navigate(`/party/${p.slug}`)}
              aria-label={p.name}
              style={{
                all: 'unset',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              <PartyPreview party={p} />
              <div>
                <strong>{p.name}</strong>
                <p style={{ margin: '4px 0 0', color: '#555' }}>{p.description}</p>
              </div>
            </button>
            <div
              style={{ fontSize: 13, color: '#666' }}
              data-testid={`occupancy-${p.slug}`}
            >
              {p.occupancy.humans} humans · {p.occupancy.agents} agents ·{' '}
              {p.occupancy.active_last_5min} active
            </div>
            <button
              type="button"
              onClick={() => setPeekSlug(p.slug)}
              style={{
                alignSelf: 'flex-start',
                padding: '6px 12px',
                borderRadius: 8,
                border: '1px solid #ccc',
                background: '#fafafa',
                cursor: 'pointer',
              }}
            >
              Peek
            </button>
          </div>
        ))}
      </div>
      {peekSlug !== null && (
        <PartyPeekModal slug={peekSlug} onClose={() => setPeekSlug(null)} />
      )}
    </main>
  );
}
```

Note: the prior card was a single `<button>` wrapping everything. We've split it so the inner `<button>` navigates and the outer `<div>` hosts the occupancy line + Peek button. The existing "navigates to /party/:slug when a card is clicked" test uses `getByRole('button', { name: /cream terrazzo lounge/i })` — the inner button retains the same accessible name via `aria-label`, so the click-to-navigate test still passes.

- [ ] **Step 4: Run lobby tests**

Run: `cd frontend && npx vitest run tests/Lobby.test.tsx`
Expected: existing tests fail because `PartyPeekModal` does not exist yet. Move on to Task 10.

- [ ] **Step 5: Do NOT commit yet** — the page imports a not-yet-created component.

---

## Task 10: Build `PartyPeekModal` (TDD)

**Files:**
- Create: `frontend/src/components/PartyPeekModal.tsx`
- Create: `frontend/tests/PartyPeekModal.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/PartyPeekModal.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PartyPeekModal from '../src/components/PartyPeekModal';

const previewResponse = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  occupancy: { humans: 2, agents: 3, total: 5, active_last_5min: 4 },
  lighting: 'dusk',
  music: { url: null, label: 'Lo-fi' },
  recent_chat: [
    { seq: 1, actor_id: 'h1', actor_username: 'alice', actor_kind: 'human', text: 'hello world', at: 1.0 },
    { seq: 2, actor_id: 'a1', actor_username: 'bot1', actor_kind: 'agent', text: 'hi back', at: 2.0 },
  ],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('PartyPeekModal', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const u = String(url);
      if (u.endsWith('/api/parties/cream-terrazzo/preview')) {
        return jsonResponse(previewResponse);
      }
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches and renders the preview payload', async () => {
    render(<PartyPeekModal slug="cream-terrazzo" onClose={() => {}} />);
    expect(
      await screen.findByText(/2 humans · 3 agents · 4 active/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/lighting:\s*dusk/i)).toBeInTheDocument();
    expect(screen.getByText(/music:\s*Lo-fi/i)).toBeInTheDocument();
    expect(screen.getByText(/alice:\s*hello world/i)).toBeInTheDocument();
    expect(screen.getByText(/bot1:\s*hi back/i)).toBeInTheDocument();
  });

  it('renders an empty-state when no recent chat', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ ...previewResponse, recent_chat: [] }),
    );
    render(<PartyPeekModal slug="cream-terrazzo" onClose={() => {}} />);
    expect(await screen.findByText(/no recent chat/i)).toBeInTheDocument();
  });

  it('calls onClose when the close button is clicked', async () => {
    const onClose = vi.fn();
    render(<PartyPeekModal slug="cream-terrazzo" onClose={onClose} />);
    await waitFor(() => screen.getByText(/Cream Terrazzo Lounge/));
    await userEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('shows an error when the fetch fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      new Response('boom', { status: 500 }),
    );
    render(<PartyPeekModal slug="cream-terrazzo" onClose={() => {}} />);
    expect(await screen.findByText(/couldn't load preview/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd frontend && npx vitest run tests/PartyPeekModal.test.tsx`
Expected: module-not-found.

- [ ] **Step 3: Implement the modal**

Create `frontend/src/components/PartyPeekModal.tsx`:

```tsx
import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';
import type { PartyPreviewResponse } from '../api/types';
import PartyPreview from './PartyPreview';

type Props = {
  slug: string;
  onClose: () => void;
};

type State =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'ready'; data: PartyPreviewResponse };

export default function PartyPeekModal({ slug, onClose }: Props) {
  const [state, setState] = useState<State>({ kind: 'loading' });

  useEffect(() => {
    let cancelled = false;
    apiGet<PartyPreviewResponse>(`/api/parties/${slug}/preview`)
      .then((data) => {
        if (!cancelled) setState({ kind: 'ready', data });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: 'error' });
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Preview ${slug}`}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: 20,
          width: 'min(560px, 92vw)',
          maxHeight: '90vh',
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {state.kind === 'loading' && <p>Loading preview…</p>}
        {state.kind === 'error' && <p>Couldn't load preview.</p>}
        {state.kind === 'ready' && (
          <>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0 }}>{state.data.name}</h2>
              <button type="button" onClick={onClose} aria-label="Close">
                ×
              </button>
            </header>
            <p style={{ margin: 0, color: '#555' }}>{state.data.description}</p>
            <PartyPreviewBody data={state.data} />
          </>
        )}
        {state.kind !== 'ready' && (
          <button type="button" onClick={onClose} aria-label="Close" style={{ alignSelf: 'flex-end' }}>
            Close
          </button>
        )}
      </div>
    </div>
  );
}

function PartyPreviewBody({ data }: { data: PartyPreviewResponse }) {
  const occ = data.occupancy;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div
        style={{
          padding: 10,
          background: '#f6f6f6',
          borderRadius: 8,
          fontSize: 14,
        }}
      >
        <div>
          {occ.humans} humans · {occ.agents} agents · {occ.active_last_5min} active
        </div>
        <div>Lighting: {data.lighting}</div>
        <div>Music: {data.music.label}</div>
      </div>
      <div>
        <strong style={{ fontSize: 13 }}>Recent chat</strong>
        {data.recent_chat.length === 0 ? (
          <p style={{ margin: '4px 0 0', color: '#888' }}>No recent chat.</p>
        ) : (
          <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
            {data.recent_chat.map((c) => (
              <li key={c.seq}>
                {c.actor_username}: {c.text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
```

Note that we render `PartyPreview` is NOT used here — the preview endpoint does not return a `PartyConfig` (we explicitly stripped walls/zones from the response for privacy and bandwidth). If you want a tiny visual badge, render only the room color stripe. The spec calls for the "PartyPreview component as the visual base — add an info panel beneath it." Since the modal opens from the lobby card where the full `PartyConfig` is still in memory, we can pass it in as an optional prop.

- [ ] **Step 4: Allow the lobby to pass the static `PartyConfig` for visuals**

Update the `Props` block and component signature in `frontend/src/components/PartyPeekModal.tsx`:

```tsx
import type { PartyConfig, PartyPreviewResponse } from '../api/types';

type Props = {
  slug: string;
  party?: PartyConfig;
  onClose: () => void;
};

export default function PartyPeekModal({ slug, party, onClose }: Props) {
  // …existing body…
        {state.kind === 'ready' && (
          <>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0 }}>{state.data.name}</h2>
              <button type="button" onClick={onClose} aria-label="Close">×</button>
            </header>
            <p style={{ margin: 0, color: '#555' }}>{state.data.description}</p>
            {party && <PartyPreview party={party} />}
            <PartyPreviewBody data={state.data} />
          </>
        )}
```

Update `frontend/src/pages/Lobby.tsx` to pass the party object:

```tsx
{peekSlug !== null && (
  <PartyPeekModal
    slug={peekSlug}
    party={parties?.find((p) => p.slug === peekSlug)}
    onClose={() => setPeekSlug(null)}
  />
)}
```

- [ ] **Step 5: Run all frontend tests for this slice**

Run: `cd frontend && npx vitest run tests/PartyPeekModal.test.tsx tests/Lobby.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/PartyPeekModal.tsx frontend/src/pages/Lobby.tsx frontend/tests/PartyPeekModal.test.tsx frontend/tests/Lobby.test.tsx
git commit -m "feat(lobby): occupancy line + Peek modal"
```

---

## Task 11: Lobby — "Peek" button opens the modal (integration TDD)

**Files:**
- Modify: `frontend/tests/Lobby.test.tsx`

- [ ] **Step 1: Add an integration test**

Append:

```tsx
  it('opens the peek modal when the Peek button is clicked', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes('/api/session/')) return jsonResponse(sessionResponse);
      if (u.endsWith('/api/parties')) return jsonResponse(partiesResponse);
      if (u.endsWith('/api/parties/cream-terrazzo/preview')) {
        return jsonResponse({
          slug: 'cream-terrazzo',
          name: 'Cream Terrazzo Lounge',
          description: 'A bright, friendly room.',
          occupancy: { humans: 2, agents: 3, total: 5, active_last_5min: 4 },
          lighting: 'day',
          music: { url: null, label: 'Music coming soon' },
          recent_chat: [],
        });
      }
      return new Response('not found', { status: 404 });
    });

    render(
      <SessionIdProvider>
        <MemoryRouter initialEntries={['/lobby']}>
          <Routes>
            <Route path="/lobby" element={<Lobby />} />
            <Route path="/party/:slug" element={<div>Party page</div>} />
          </Routes>
        </MemoryRouter>
      </SessionIdProvider>,
    );

    const peek = await screen.findByRole('button', { name: /peek/i });
    await userEvent.click(peek);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(await screen.findByText(/no recent chat/i)).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test**

Run: `cd frontend && npx vitest run tests/Lobby.test.tsx`
Expected: passes (modal wiring landed in Task 10).

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/Lobby.test.tsx
git commit -m "test(lobby): assert Peek button opens modal"
```

---

## Task 12: Agent guide — mention occupancy + preview

**Files:**
- Modify: `backend/app/routes/agent_guide.py`
- Modify: `backend/tests/test_agent_guide_content.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_agent_guide_content.py`:

```python
def test_agent_guide_mentions_occupancy_and_preview(client):
    res = client.get("/api/agent-guide")
    assert res.status_code == 200
    body = res.text
    assert "occupancy" in body
    assert "/api/parties/{slug}/preview" in body
    assert "active_last_5min" in body
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd backend && pytest tests/test_agent_guide_content.py::test_agent_guide_mentions_occupancy_and_preview -v`
Expected: assertion fails.

- [ ] **Step 3: Edit the guide content**

Open `backend/app/routes/agent_guide.py`, find the section describing `/api/parties` (search for "GET /api/parties"). Add the following block immediately after that subsection. If no such subsection exists, place this near the top of the routes list:

```text
### Discovery

`GET /api/parties` — list parties. Each entry now includes an `occupancy`
object:

```json
{
  "humans": 2,
  "agents": 3,
  "total": 5,
  "active_last_5min": 4
}
```

`active_last_5min` counts participants currently in the room who emitted a
`join`, `move`, `chat`, or `reaction` event in the last 300 seconds.

`GET /api/parties/{slug}/preview` — public peek; **does not require an
agent_id**. Returns `occupancy`, `lighting`, `music`, and `recent_chat`
(the last 5 room-wide chats). It does NOT include participant identities,
sticky notes, drawboard strokes, or DMs. Use this to decide whether to
switch parties without joining.
```

Keep whatever the file's existing formatting convention is (the file is markdown returned as text). If the guide uses Python triple-quoted strings, escape the inner triple backticks accordingly — match the existing style for code samples.

- [ ] **Step 4: Run test to confirm pass**

Run: `cd backend && pytest tests/test_agent_guide_content.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_content.py
git commit -m "docs(agent-guide): document occupancy + preview"
```

---

## Task 13: Full-suite smoke test

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && pytest -x --tb=short`
Expected: all pass. If a pre-existing test relied on the old shape of `PartiesListResponse` (no `occupancy` key), update it: `entry["occupancy"]` is now a required key on every list response. Search with `grep -rn "/api/parties" backend/tests` and fix any assertion that expected the old shape.

- [ ] **Step 2: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: all pass. If any other test mocks `/api/parties` and feeds entries without `occupancy`, add `occupancy: { humans: 0, agents: 0, total: 0, active_last_5min: 0 }` to those mocks. Likely affected: `frontend/tests/App.test.tsx`.

- [ ] **Step 3: Manual smoke check**

Run the dev server (`cd backend && uvicorn app.main:app` in one shell, `cd frontend && npm run dev` in another).

- Open `http://localhost:5173/lobby`. Each card shows the occupancy line.
- Click **Peek**. Modal opens, shows occupancy + lighting + music + "No recent chat."
- In a second tab, sign in and join the cream-terrazzo party. Send one chat.
- Close & reopen the Peek modal on the first tab. The chat appears.
- Confirm the modal does NOT show any participant identities other than the chat author and no notes/strokes.

- [ ] **Step 4: Final commit if anything was fixed**

```bash
git add -u
git commit -m "chore(parties): fix collateral test mocks after occupancy rollout"
```

(Skip if nothing was changed.)

---

## Self-review checklist

1. **Spec coverage** — Every spec item is mapped:
   - `GET /api/parties` occupancy → Task 3.
   - empty room / mixed populations / idle counting → Task 2 tests.
   - Public `/preview` → Task 5.
   - Recent chat (5, room-wide only, no proximity) → Task 6 + privacy guard test.
   - lighting + music → Task 5 / Task 7.
   - Does NOT include participant list/notes/drawboard/DMs → Task 5 shape test.
   - Lobby UI occupancy line → Task 9.
   - Peek button + lightweight modal → Tasks 10, 11.
   - PartyPreview component as visual base → Task 10 Step 4.

2. **Placeholder scan** — All "if exists" hooks are guarded with `getattr` and tested with the existing static field, so the plan works whether spec #07 has landed or not. No "TBD" or "similar to" placeholders.

3. **Type consistency** — `Occupancy` shape is identical wherever it appears (backend model, list endpoint, preview endpoint, frontend type, lobby UI string). `PartyPreviewResponse` field names match between Pydantic (`recent_chat`, `active_last_5min`) and TS type. `compute_occupancy` returns a plain dict and is wrapped with `Occupancy(**...)` at every callsite.

4. **Proximity safety** — Preview chat objects use the `PartyPreviewChat` model which has NO `x`, `y`, `scope`, `audience`, `audience_ids`, or `heard_by` fields. Task 6 Step 3 adds a regression test for this. The preview pulls from `world.recent_chat(limit=5)`, which today returns only `ChatEvent` rows; if spec #02 later adds proximity metadata to `ChatEvent.model_dump()`, the explicit field-pick in the route still strips it.
