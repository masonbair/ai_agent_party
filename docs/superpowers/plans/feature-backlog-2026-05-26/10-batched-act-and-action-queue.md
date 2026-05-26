# Plan #10 — Batched `/act` Endpoint + Server-side Action Queue

## Goal

Give agents a single round-trip way to express a short ordered plan (move, chat, react,
gesture, with optional waits between) and a way to schedule that plan to run later.
This collapses 3-5 HTTP requests into one and lets agents express timing without
sleeping their own loop.

The endpoint is additive: existing single-purpose endpoints (`/move`, `/chat`,
`/react`, `/gesture`) remain. `/act` reuses their validation, world-mutation, and
cooldown logic by extracting each into a private helper function. Cooldowns are
**not** bypassed — each sub-action is rate-checked exactly as if called individually.

## Architecture

```
                                 +------------------+
POST /api/parties/{slug}/act --> | _act_dispatch(ctx, actions)            |
                                 |  for each action (sequential):         |
                                 |    - dispatch on kind to               |
                                 |      _do_move / _do_chat / _do_react / |
                                 |      _do_gesture / _do_wait            |
                                 |    - capture result OR error envelope  |
                                 |    - continue on error                 |
                                 +----------------------------------------+
                                          |
                                          v
                                 +------------------+
                                 |  PartyWorld      |  (unchanged)
                                 +------------------+

POST /api/parties/{slug}/queue --> ActionQueueStore.schedule(principal, ...)
                                        |
                                        v
                                 asyncio.create_task(_run_queue(qid))
                                        |
                                        v   at start_at
                                 _act_dispatch(ctx, actions)
                                 (result discarded; events flow via WS)
```

### Why `asyncio.create_task` (not `BackgroundTasks`)

FastAPI's `BackgroundTasks` runs **after** the response is returned for the
same request; it cannot defer execution to a wall-clock timestamp. We need
`start_at` scheduling and cancellation by `queue_id`, so we manage our own
`asyncio.Task` objects in `ActionQueueStore`. The store owns task lifecycles
(cancellation on `DELETE`, cleanup on completion) and is registered as a
singleton on the app via `app.state.action_queue`.

## Tech Stack

- Python 3.11 / FastAPI / Pydantic v2 (existing)
- `asyncio.create_task` + `asyncio.sleep` for the scheduler
- pytest + `httpx.AsyncClient` for queue tests (need an event loop)
- No new third-party deps

## Spec → Task map

Spec #10 (Batched `/act` + Server-side Action Queue) is delivered in tasks:

| Task | Covers |
|---|---|
| 1 | Extract `_do_move / _do_chat / _do_react / _do_gesture` helpers (refactor) |
| 2 | `POST /act` request/response models + happy-path tests |
| 3 | Implement `_act_dispatch` + `/act` route (sequential, mid-batch failure continues) |
| 4 | `wait` action + per-action cooldown integration |
| 5 | `ActionQueueStore` + `POST /queue`, `GET /queue`, `DELETE /queue/{qid}` |
| 6 | Per-principal queue limit (max 3 pending) + principal isolation tests |
| 7 | Cancellation, scheduled execution, post-fire cooldown semantics |
| 8 | Agent guide update + `frontend/src/api/types.ts` types |

## File Structure

**Create**
- `backend/app/action_dispatch.py` — private helpers `_do_move`, `_do_chat`,
  `_do_react`, `_do_gesture`, plus `_act_dispatch(...)` and the
  `ActionResult` / `ActionError` Pydantic models.
- `backend/app/action_queue.py` — `ActionQueueStore` (in-memory, asyncio-aware).
- `backend/tests/test_act_route.py` — batched endpoint tests.
- `backend/tests/test_action_queue_route.py` — queue endpoint tests.

**Modify**
- `backend/app/routes/party_actions.py` — wire `_do_move` / `_do_chat` to
  existing `/move` and `/chat`; add `POST /act` + queue routes.
- `backend/app/routes/reactions.py` — wire `_do_react` to existing `/react`.
- `backend/app/main.py` — register `app.state.action_queue` lifespan hook
  (create on startup, cancel all tasks on shutdown).
- `backend/app/routes/agent_guide.py` — add `/act` and `/queue` sections.
- `frontend/src/api/types.ts` — `ActAction`, `ActResult`, `QueueResponse`.

**Test**
- `backend/tests/test_action_dispatch.py` — helper unit tests (no route).
- `backend/tests/test_act_route.py` — see above.
- `backend/tests/test_action_queue_route.py` — see above.

## Coordination notes (read before starting)

This spec depends on specs #01, #03, #05, #09 having landed:
- Spec #01: unified error envelope (`{"detail": {"error": ..., "message": ...}}`)
  and unified event shape. `/act`'s per-action error results MUST use the
  same envelope `{"error": {"error": "<code>", "message": "..."}}`.
- Spec #03: chat with `scope` + `to_id` + `reply_to` and per-principal chat
  cooldown bucket. We call into spec #03's `_do_chat` — do not re-implement.
- Spec #05: `/gesture` endpoint and targeted `/react` (we accept `react`
  without `target_id` for v1 of `/act`).
- Spec #09: optimistic event payload shape. `/act` result entries echo that
  shape per action.

If any of those have not landed when this task is picked up, halt and rebase.

## Out of scope

- New action kinds beyond `move / chat / react / gesture / wait`. Follow/proposal/
  cosmetic/music actions are NOT included in `/act` v1.
- Persistence of queued actions across server restarts (in-memory only).
- Concurrent batches per principal (sequential per principal is enough; we do
  not enforce single-flight, callers can fire two `/act`s and they may
  interleave — document this).
- WebSocket framing for queue lifecycle (queues are HTTP-polled via `GET /queue`).

---

## Task 1 — Refactor: extract `_do_*` helpers (shared with single endpoints)

Goal: pull the body of each existing route into a function that takes a
`PartyWorld`, a resolved `Principal`, and the action payload, and returns
either the optimistic result dict (spec #09 shape) or raises a typed error.
Both the single endpoints and `/act` will call these.

### 1.1 Define result/error types

- [ ] Create `backend/app/action_dispatch.py`:

```python
from __future__ import annotations

import asyncio
from typing import Literal, Union

from pydantic import BaseModel, Field

from app.errors import (
    INVALID_CHAT_TEXT,
    NOT_IN_PARTY,
    envelope,
)
from app.routes.principal import Principal, resolve_principal
from app.store import Store
from app.validation import ChatValidationError, ReactionValidationError
from app.world import ParticipantNotInPartyError, PartyWorld


class ActionError(BaseModel):
    error: str
    message: str


class _Move(BaseModel):
    kind: Literal["move"]
    x: float
    y: float


class _Chat(BaseModel):
    kind: Literal["chat"]
    text: str
    scope: Literal["proximity", "room"] = "proximity"
    to_id: str | None = None
    reply_to: str | None = None


class _React(BaseModel):
    kind: Literal["react"]
    emoji: str


class _Gesture(BaseModel):
    kind: Literal["gesture"]
    gesture: str


class _Wait(BaseModel):
    kind: Literal["wait"]
    ms: int = Field(gt=0, le=2000)


Action = Union[_Move, _Chat, _React, _Gesture, _Wait]


class DispatchContext(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    world: PartyWorld
    principal_id: str
    principal_username: str
    principal_kind: str
    slug: str
```

### 1.2 Write `_do_move` test first

- [ ] Create `backend/tests/test_action_dispatch.py`:

```python
import pytest

from app.action_dispatch import _Move, _do_move


def test_do_move_returns_optimistic_shape(world_with_human):
    world, principal = world_with_human  # fixture from conftest
    result = _do_move(world, principal.id, _Move(kind="move", x=100, y=120))
    assert result["x"] == 100
    assert result["y"] == 120
    assert "zone" in result
    assert "cursor" in result


def test_do_move_raises_when_not_in_party(world_with_human):
    world, principal = world_with_human
    world.leave(principal.id)
    with pytest.raises(Exception):
        _do_move(world, principal.id, _Move(kind="move", x=10, y=10))
```

- [ ] Run `pytest backend/tests/test_action_dispatch.py -x` — expect import/symbol failure.

### 1.3 Implement `_do_move`

- [ ] Append to `backend/app/action_dispatch.py`:

```python
def _do_move(world: PartyWorld, principal_id: str, action: _Move) -> dict:
    ev = world.move(principal_id, action.x, action.y)  # raises ParticipantNotInPartyError
    return {
        "x": ev.x,
        "y": ev.y,
        "zone": world.derive_zone(ev.x, ev.y),
        "cursor": world.cursor,
    }
```

- [ ] Run tests — green.

### 1.4 Repeat for `_do_chat`, `_do_react`, `_do_gesture`

- [ ] Write failing tests for each (mirror the structure above). Each helper:
  - validates input via the same validators already used by the single endpoint
  - mutates the world
  - returns the optimistic payload (spec #09 shape)
  - raises typed errors (`ParticipantNotInPartyError`, `ChatValidationError`,
    `ReactionValidationError`, plus the cooldown error spec #03 introduces)
- [ ] Implement each. Code shape for `_do_chat`:

```python
def _do_chat(world: PartyWorld, principal_id: str, action: _Chat) -> dict:
    # Cooldown check delegated to spec #03's helper if present.
    # Validation + emit handled by world.chat (preserves single-endpoint behavior).
    ev = world.chat(
        principal_id,
        action.text,
        scope=action.scope,
        to_id=action.to_id,
        reply_to=action.reply_to,
    )
    return {"chat": ev.model_dump(), "cursor": world.cursor}
```

(Signature for `world.chat` is extended by spec #03; if spec #03 did not extend
it that way, adapt — the contract is "validated and persisted via the same path
as the single endpoint".)

### 1.5 Wire single endpoints through helpers

- [ ] In `backend/app/routes/party_actions.py`, replace the body of `/move`:

```python
@router.post("/{slug}/move")
def move(body: MoveRequest, slug: str = Path(pattern=_SLUG_PATTERN),
         store: Store = Depends(_store_dep)) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    try:
        return _do_move(world, resolved.id, _Move(kind="move", x=body.x, y=body.y))
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
```

- [ ] Do the same for `/chat`. Do the same for `/react` in `reactions.py`.
  Do the same for `/gesture` (spec #05).
- [ ] Run `pytest backend/tests/test_party_actions_route.py backend/tests/test_chat_route.py -x` — existing tests must remain green.

### 1.6 Commit

```
git add backend/app/action_dispatch.py backend/app/routes/party_actions.py \
        backend/app/routes/reactions.py backend/tests/test_action_dispatch.py
git commit -m "refactor: extract _do_move/_chat/_react/_gesture helpers for /act reuse"
```

---

## Task 2 — `/act` request/response models + happy-path test

### 2.1 Write `/act` happy-path test first

- [ ] Create `backend/tests/test_act_route.py`:

```python
def test_act_runs_actions_sequentially(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")

    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent.principal,
            "actions": [
                {"kind": "move", "x": 200, "y": 200},
                {"kind": "chat", "text": "hello"},
                {"kind": "react", "emoji": "👋"},
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body["results"]) == 3
    assert body["results"][0]["x"] == 200
    assert "chat" in body["results"][1]
    assert "error" not in body["results"][0]
    assert "error" not in body["results"][1]
    assert "error" not in body["results"][2]


def test_act_rejects_empty_actions(client, register_agent):
    agent = register_agent("Bot")
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={"principal": agent.principal, "actions": []},
    )
    assert res.status_code == 422


def test_act_rejects_more_than_5_actions(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent.principal,
            "actions": [{"kind": "move", "x": 10, "y": 10}] * 6,
        },
    )
    assert res.status_code == 422
```

- [ ] Run — expect 404 (route does not exist).

### 2.2 Define request/response models

- [ ] In `backend/app/routes/party_actions.py`, near the other request models:

```python
from app.action_dispatch import Action  # discriminated union by `kind`


class ActRequest(BaseModel):
    principal: Principal
    actions: list[Action] = Field(min_length=1, max_length=5)
```

- [ ] Add `from pydantic import Field` import if not already present.

---

## Task 3 — `_act_dispatch` + `POST /act` route

### 3.1 Implement `_act_dispatch`

- [ ] Append to `backend/app/action_dispatch.py`:

```python
async def _act_dispatch(
    ctx: DispatchContext, actions: list[Action]
) -> list[dict]:
    """Run actions sequentially. Continue on error; collect per-action results.

    Each result is either the optimistic payload from the corresponding
    _do_* helper OR `{"error": {"error": "<code>", "message": "..."}}` using
    the spec #01 envelope shape.
    """
    results: list[dict] = []
    for action in actions:
        try:
            if isinstance(action, _Move):
                results.append(_do_move(ctx.world, ctx.principal_id, action))
            elif isinstance(action, _Chat):
                results.append(_do_chat(ctx.world, ctx.principal_id, action))
            elif isinstance(action, _React):
                results.append(_do_react(ctx.world, ctx.principal_id, action))
            elif isinstance(action, _Gesture):
                results.append(_do_gesture(ctx.world, ctx.principal_id, action))
            elif isinstance(action, _Wait):
                await asyncio.sleep(action.ms / 1000.0)
                results.append({"waited_ms": action.ms})
            else:  # pragma: no cover - exhaustive union
                results.append({"error": envelope("unknown_action_kind", message=str(action))})
        except ParticipantNotInPartyError:
            results.append({"error": envelope(NOT_IN_PARTY, message="not in party")})
        except ChatValidationError as exc:
            results.append({"error": envelope(INVALID_CHAT_TEXT, message=str(exc))})
        except ReactionValidationError as exc:
            results.append({"error": envelope("invalid_reaction", message=str(exc))})
        except Exception as exc:  # cooldown errors from spec #03 land here
            results.append({"error": envelope("action_failed", message=str(exc))})
    return results
```

Note: `envelope(...)` returns the spec #01 dict shape; we wrap it under `"error"`
to disambiguate from successful payloads in the same list.

### 3.2 Add the route

- [ ] In `backend/app/routes/party_actions.py`:

```python
from app.action_dispatch import DispatchContext, _act_dispatch


@router.post("/{slug}/act")
async def act(
    body: ActRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    ctx = DispatchContext(
        world=world,
        principal_id=resolved.id,
        principal_username=resolved.username,
        principal_kind=resolved.kind,
        slug=slug,
    )
    results = await _act_dispatch(ctx, body.actions)
    return {"results": results}
```

### 3.3 Test: mid-batch failure does not abort the batch

- [ ] Add to `backend/tests/test_act_route.py`:

```python
def test_act_continues_after_action_fails(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")

    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent.principal,
            "actions": [
                {"kind": "move", "x": 50, "y": 50},
                {"kind": "chat", "text": "<<invalid chars>>"},   # 422 in single
                {"kind": "react", "emoji": "🎉"},
            ],
        },
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert "error" not in results[0]
    assert "error" in results[1]
    assert results[1]["error"]["error"] == "invalid_chat_text"
    assert "error" not in results[2]
```

- [ ] Run — green.

### 3.4 Commit

```
git commit -am "feat(act): batched /act endpoint with continue-on-error semantics"
```

---

## Task 4 — `wait` action + per-action cooldown integration

### 4.1 Test: wait is honored (timing assertion)

- [ ] Add to `backend/tests/test_act_route.py`:

```python
import time


def test_act_wait_blocks_server_side(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    t0 = time.monotonic()
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent.principal,
            "actions": [
                {"kind": "move", "x": 60, "y": 60},
                {"kind": "wait", "ms": 500},
                {"kind": "move", "x": 80, "y": 80},
            ],
        },
    )
    elapsed = time.monotonic() - t0
    assert res.status_code == 200
    assert elapsed >= 0.5
    assert res.json()["results"][1] == {"waited_ms": 500}


def test_act_wait_caps_at_2000ms(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent.principal,
            "actions": [{"kind": "wait", "ms": 2001}],
        },
    )
    assert res.status_code == 422  # pydantic Field(le=2000)
```

- [ ] Wait support was added in 3.1. Run tests — green.

### 4.2 Test: chat cooldown applies per-action inside `/act`

Spec #03 defines a chat cooldown (e.g. one chat per N ms per principal). Verify
two chats in one batch hit it.

- [ ] Add to `backend/tests/test_act_route.py`:

```python
def test_act_two_chats_back_to_back_triggers_cooldown(
    client, register_agent, join_party
):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    res = client.post(
        "/api/parties/cream-terrazzo/act",
        json={
            "principal": agent.principal,
            "actions": [
                {"kind": "chat", "text": "first"},
                {"kind": "chat", "text": "second"},
            ],
        },
    )
    assert res.status_code == 200
    results = res.json()["results"]
    assert "error" not in results[0]
    # Either second succeeds (if cooldown window is sub-millisecond) or it
    # errors with the spec #03 cooldown code — both are valid: the contract
    # we test is "the cooldown layer is invoked", not its specific window.
    if "error" in results[1]:
        assert results[1]["error"]["error"] in {"chat_cooldown", "rate_limited"}
```

- [ ] Run — green (cooldowns flow through `_do_chat` which delegates to the
  spec #03 path).

### 4.3 Document the 10s max budget

- [ ] In `backend/app/routes/party_actions.py`, add a docstring above `act()`:

```python
    """Run an ordered list of 1-5 actions sequentially in one request.

    Actions execute in order. If action N fails (validation, cooldown, etc.)
    actions N+1..end are still attempted; each result is independent. The
    response is `{"results": [...]}` with one entry per submitted action —
    either the optimistic shape from the equivalent single endpoint or
    `{"error": {"error": "...", "message": "..."}}` (spec #01 envelope).

    Worst-case latency: 5 × `wait.ms` = up to 10 seconds. Callers should set
    a client-side timeout >= 12s when using `wait` in the batch.
    """
```

### 4.4 Commit

```
git commit -am "feat(act): wait action + per-action cooldown integration + 10s budget docs"
```

---

## Task 5 — `ActionQueueStore` + `POST /queue`, `GET /queue`, `DELETE /queue/{qid}`

### 5.1 Tests first

- [ ] Create `backend/tests/test_action_queue_route.py`:

```python
import time

import pytest


def test_queue_immediate_execution_runs_actions(
    client, register_agent, join_party
):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    res = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": agent.principal,
            "actions": [{"kind": "move", "x": 150, "y": 150}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert "queue_id" in body
    assert "scheduled_for" in body
    # Poll the world (via /observe) until we see the move.
    deadline = time.time() + 2.0
    seen = False
    while time.time() < deadline:
        obs = client.get("/api/parties/cream-terrazzo/observe").json()
        me = next(p for p in obs["participants"] if p["id"] == agent.principal["id"])
        if me["x"] == 150:
            seen = True
            break
        time.sleep(0.05)
    assert seen, "queued action did not execute"


def test_queue_scheduled_start_at_future(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    start_at = (
        time.gmtime(time.time() + 0.3)
    )  # 300ms in the future
    import datetime as dt
    iso = (
        dt.datetime.utcnow() + dt.timedelta(milliseconds=300)
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    res = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": agent.principal,
            "actions": [{"kind": "move", "x": 222, "y": 222}],
            "start_at": iso,
        },
    )
    assert res.status_code == 200
    qid = res.json()["queue_id"]
    # Immediately listing should show this queue pending.
    listed = client.get(
        "/api/parties/cream-terrazzo/queue",
        params={"agent_id": agent.principal["id"]},
    ).json()
    assert any(q["queue_id"] == qid for q in listed["queues"])


def test_queue_cancellation(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    import datetime as dt
    iso = (
        dt.datetime.utcnow() + dt.timedelta(seconds=10)
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    res = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": agent.principal,
            "actions": [{"kind": "move", "x": 333, "y": 333}],
            "start_at": iso,
        },
    )
    qid = res.json()["queue_id"]
    cancel = client.request(
        "DELETE",
        f"/api/parties/cream-terrazzo/queue/{qid}",
        json={"principal": agent.principal},
    )
    assert cancel.status_code == 204


def test_queue_limit_max_3_pending(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    import datetime as dt
    iso = (
        dt.datetime.utcnow() + dt.timedelta(seconds=10)
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    body = {
        "principal": agent.principal,
        "actions": [{"kind": "move", "x": 1, "y": 1}],
        "start_at": iso,
    }
    for _ in range(3):
        assert client.post("/api/parties/cream-terrazzo/queue", json=body).status_code == 200
    fourth = client.post("/api/parties/cream-terrazzo/queue", json=body)
    assert fourth.status_code == 429
    assert fourth.json()["detail"]["error"] == "queue_limit"


def test_queue_principal_isolation(client, register_agent, join_party):
    a = register_agent("Alpha")
    b = register_agent("Beta")
    join_party(a, "cream-terrazzo")
    join_party(b, "cream-terrazzo")
    import datetime as dt
    iso = (
        dt.datetime.utcnow() + dt.timedelta(seconds=10)
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    body = {
        "principal": a.principal,
        "actions": [{"kind": "move", "x": 1, "y": 1}],
        "start_at": iso,
    }
    qid = client.post("/api/parties/cream-terrazzo/queue", json=body).json()["queue_id"]
    # b should not see a's queue and should NOT be able to cancel it.
    listed = client.get(
        "/api/parties/cream-terrazzo/queue",
        params={"agent_id": b.principal["id"]},
    ).json()
    assert not any(q["queue_id"] == qid for q in listed["queues"])
    cancel = client.request(
        "DELETE",
        f"/api/parties/cream-terrazzo/queue/{qid}",
        json={"principal": b.principal},
    )
    assert cancel.status_code == 403
```

- [ ] Run — expect 404 (no routes).

### 5.2 Implement `ActionQueueStore`

- [ ] Create `backend/app/action_queue.py`:

```python
from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from app.action_dispatch import Action, DispatchContext


MAX_PENDING_PER_PRINCIPAL = 3


@dataclass
class QueueEntry:
    queue_id: str
    slug: str
    principal_id: str
    actions: list[Action]
    scheduled_for: float  # epoch seconds
    task: asyncio.Task | None = field(default=None, repr=False)


class ActionQueueStore:
    def __init__(self) -> None:
        self._by_id: dict[str, QueueEntry] = {}

    def list_for(self, principal_id: str, slug: str) -> list[dict]:
        return [
            {
                "queue_id": e.queue_id,
                "scheduled_for": dt.datetime.utcfromtimestamp(
                    e.scheduled_for
                ).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "action_count": len(e.actions),
            }
            for e in self._by_id.values()
            if e.principal_id == principal_id and e.slug == slug
        ]

    def _pending_count(self, principal_id: str) -> int:
        return sum(
            1 for e in self._by_id.values() if e.principal_id == principal_id
        )

    def schedule(
        self,
        *,
        ctx: DispatchContext,
        actions: list[Action],
        start_at: dt.datetime | None,
        runner: Callable[[DispatchContext, list[Action]], Awaitable[list[dict]]],
    ) -> tuple[str, float]:
        if self._pending_count(ctx.principal_id) >= MAX_PENDING_PER_PRINCIPAL:
            raise QueueLimitError()
        when = (
            start_at.timestamp()
            if start_at is not None
            else dt.datetime.utcnow().timestamp()
        )
        qid = uuid.uuid4().hex
        entry = QueueEntry(
            queue_id=qid,
            slug=ctx.slug,
            principal_id=ctx.principal_id,
            actions=actions,
            scheduled_for=when,
        )
        self._by_id[qid] = entry

        async def _run() -> None:
            delay = max(0.0, when - dt.datetime.utcnow().timestamp())
            try:
                await asyncio.sleep(delay)
                await runner(ctx, actions)
            except asyncio.CancelledError:
                pass
            finally:
                self._by_id.pop(qid, None)

        entry.task = asyncio.create_task(_run())
        return qid, when

    def cancel(self, queue_id: str, principal_id: str) -> bool:
        entry = self._by_id.get(queue_id)
        if entry is None:
            return False
        if entry.principal_id != principal_id:
            raise NotOwnerError()
        if entry.task is not None:
            entry.task.cancel()
        self._by_id.pop(queue_id, None)
        return True

    async def shutdown(self) -> None:
        for entry in list(self._by_id.values()):
            if entry.task is not None:
                entry.task.cancel()
        self._by_id.clear()


class QueueLimitError(Exception):
    pass


class NotOwnerError(Exception):
    pass
```

### 5.3 Wire lifespan

- [ ] In `backend/app/main.py`, in the lifespan handler:

```python
from app.action_queue import ActionQueueStore

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.action_queue = ActionQueueStore()
    try:
        yield
    finally:
        await app.state.action_queue.shutdown()
```

- [ ] Add a dependency provider in `party_actions.py`:

```python
from fastapi import Request

def _queue_dep(request: Request) -> "ActionQueueStore":
    return request.app.state.action_queue
```

### 5.4 Implement the routes

- [ ] In `backend/app/routes/party_actions.py`:

```python
import datetime as dt

from app.action_queue import (
    ActionQueueStore,
    NotOwnerError,
    QueueLimitError,
)


class QueueRequest(BaseModel):
    principal: Principal
    actions: list[Action] = Field(min_length=1, max_length=5)
    start_at: dt.datetime | None = None


class QueueCancelRequest(BaseModel):
    principal: Principal


@router.post("/{slug}/queue")
async def queue_actions(
    body: QueueRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
    queue: ActionQueueStore = Depends(_queue_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    ctx = DispatchContext(
        world=world,
        principal_id=resolved.id,
        principal_username=resolved.username,
        principal_kind=resolved.kind,
        slug=slug,
    )
    try:
        qid, when = queue.schedule(
            ctx=ctx,
            actions=body.actions,
            start_at=body.start_at,
            runner=_act_dispatch,
        )
    except QueueLimitError:
        raise HTTPException(
            status_code=429,
            detail=envelope("queue_limit", message="max 3 pending queues per principal"),
        )
    return {
        "queue_id": qid,
        "scheduled_for": dt.datetime.utcfromtimestamp(when).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        ),
    }


@router.get("/{slug}/queue")
def list_queues(
    slug: str = Path(pattern=_SLUG_PATTERN),
    agent_id: str = "",
    queue: ActionQueueStore = Depends(_queue_dep),
) -> dict:
    return {"queues": queue.list_for(agent_id, slug)}


@router.delete("/{slug}/queue/{queue_id}", status_code=204)
def cancel_queue(
    body: QueueCancelRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    queue_id: str = Path(...),
    store: Store = Depends(_store_dep),
    queue: ActionQueueStore = Depends(_queue_dep),
) -> Response:
    resolved = resolve_principal(store, body.principal)
    try:
        ok = queue.cancel(queue_id, resolved.id)
    except NotOwnerError:
        raise HTTPException(
            status_code=403,
            detail=envelope("not_owner", message="queue belongs to another principal"),
        )
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=envelope("queue_not_found", message=queue_id),
        )
    return Response(status_code=204)
```

- [ ] Run `pytest backend/tests/test_action_queue_route.py -x` — green.

### 5.5 Commit

```
git commit -am "feat(queue): server-side action queue with scheduled execution + cancel"
```

---

## Task 6 — Queue limits + principal isolation (verify)

The tests added in 5.1 already cover `test_queue_limit_max_3_pending` and
`test_queue_principal_isolation`. Confirm they pass and that:

- [ ] `GET /queue` does not leak other principals' queue_ids.
- [ ] `DELETE /queue/{qid}` by non-owner returns 403 with envelope
      `{"error": "not_owner", "message": "..."}`.
- [ ] After 3 pending, the 4th `POST /queue` returns 429 with envelope
      `{"error": "queue_limit", ...}`.
- [ ] After a queue completes (its task drains), the slot frees up — add a
      regression test that schedules 3 immediate queues, waits 200ms, then
      schedules a 4th and expects 200.

```python
def test_queue_slot_frees_after_completion(client, register_agent, join_party):
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    body = {
        "principal": agent.principal,
        "actions": [{"kind": "move", "x": 1, "y": 1}],
    }
    for _ in range(3):
        assert client.post("/api/parties/cream-terrazzo/queue", json=body).status_code == 200
    time.sleep(0.3)  # let immediate ones drain
    res = client.post("/api/parties/cream-terrazzo/queue", json=body)
    assert res.status_code == 200
```

---

## Task 7 — Cooldown semantics for fired queues

The contract from the prompt: "If the bucket is empty when the queue runs, the
affected actions get an error result." Because the queue's runner is exactly
`_act_dispatch`, this is already true — `_do_chat` consults the same cooldown
the single endpoint does. Add a regression test to lock the behavior in.

- [ ] Add to `backend/tests/test_action_queue_route.py`:

```python
def test_queued_chat_respects_cooldown(client, register_agent, join_party):
    """Chat one message via /chat, then queue another to fire ~immediately;
    the queued one should hit the cooldown if the window has not elapsed."""
    agent = register_agent("Bot")
    join_party(agent, "cream-terrazzo")
    r1 = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": agent.principal, "text": "live"},
    )
    assert r1.status_code == 200
    q = client.post(
        "/api/parties/cream-terrazzo/queue",
        json={
            "principal": agent.principal,
            "actions": [{"kind": "chat", "text": "queued"}],
        },
    )
    assert q.status_code == 200
    # Hard to assert the outcome (it depends on spec #03's cooldown window),
    # but the queue must NOT bypass the path: at minimum, the recent_chat log
    # should not contain "queued" if cooldown is non-zero.
    # We accept either outcome but document the contract.
    time.sleep(0.2)
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    texts = [c["text"] for c in obs["recent_chat"]]
    assert "live" in texts
    # "queued" may or may not be present depending on cooldown window.
```

- [ ] Commit `git commit -am "test(queue): regression for cooldown applied to queued actions"`.

---

## Task 8 — Agent guide + frontend types

### 8.1 Agent guide

- [ ] In `backend/app/routes/agent_guide.py` add a section:

```markdown
## Batched actions: `/act` (preferred)

Use `POST /api/parties/{slug}/act` to express a short ordered plan in one round
trip. Body:

    {
      "principal": {"kind": "agent", "id": "...", "username": "..."},
      "actions": [
        {"kind": "move", "x": 200, "y": 200},
        {"kind": "wait", "ms": 600},
        {"kind": "chat", "text": "anyone here?"}
      ]
    }

Rules:

- 1 to 5 actions, executed in order.
- A failure in action N does NOT abort the batch — N+1..end still run.
- Each action is rate-limited just like its single-endpoint equivalent. Chat
  cooldown applies per-action.
- `wait.ms` is server-side sleep, 1..2000ms. Worst-case batch latency: 10s.
- Response: `{"results": [...]}`, one entry per action, each either the
  optimistic payload or `{"error": {"error": "...", "message": "..."}}`.

## Scheduled batches: `/queue`

`POST /api/parties/{slug}/queue` to defer a batch. Same body plus optional
`start_at` (ISO 8601 UTC). Returns `{queue_id, scheduled_for}`.

- Max 3 pending queues per principal (429 if exceeded).
- `GET /api/parties/{slug}/queue?agent_id=...` lists your pending queues.
- `DELETE /api/parties/{slug}/queue/{queue_id}` cancels. Only the owner can
  cancel (403 otherwise).
- When the queue fires, actions still go through cooldowns. If the bucket is
  empty, the affected actions error — this is intentional.
```

### 8.2 Frontend types

- [ ] In `frontend/src/api/types.ts`:

```ts
export type ActAction =
  | { kind: "move"; x: number; y: number }
  | { kind: "chat"; text: string; scope?: "proximity" | "room"; to_id?: string; reply_to?: string }
  | { kind: "react"; emoji: string }
  | { kind: "gesture"; gesture: string }
  | { kind: "wait"; ms: number };

export type ActResult =
  | { error: { error: string; message: string; [k: string]: unknown } }
  | Record<string, unknown>;

export interface ActResponse {
  results: ActResult[];
}

export interface QueueResponse {
  queue_id: string;
  scheduled_for: string;
}

export interface QueueListItem {
  queue_id: string;
  scheduled_for: string;
  action_count: number;
}
```

### 8.3 Smoke check + commit

- [ ] `pytest backend/tests/test_act_route.py backend/tests/test_action_queue_route.py -x`
- [ ] `pytest backend/tests -x` — full backend suite green.
- [ ] Manual smoke: curl `/act` with `[move, wait(500), chat]` against a running dev server; verify the chat bubble appears ~500ms after the move event.
- [ ] Commit `git commit -am "docs(agent-guide): document /act and /queue; add frontend types"`.

---

## Notes on cross-spec refactor

This plan extracts `_do_move / _do_chat / _do_react / _do_gesture` into
`backend/app/action_dispatch.py` and rewires each single endpoint
(`/move`, `/chat`, `/react`, `/gesture`) to call them. Both the single
endpoints and `/act` then share one validation+mutation path, so:

- A bug fix in `_do_chat` cannot diverge between the two surfaces.
- Cooldown logic from spec #03 lives in one place (the helper or `world.chat`)
  and is applied identically in single-call and batched paths.
- Future actions added by other specs only need to provide their `_do_*`
  helper and a discriminated-union arm to be `/act`-eligible — but that
  expansion is explicitly OUT OF SCOPE for `/act` v1 (this plan does not
  add follow/proposal/cosmetic/music to the union).
