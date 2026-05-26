# Chat Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich `POST /chat` with first-class mentions, directed messages, replies, room-vs-proximity scope, structured validation errors, and a per-actor token-bucket cooldown — all on top of the unified event shape (spec #01) and proximity defaults (spec #02).

**Architecture:** Augment `ChatEvent` with optional `mentions: list[str]`, `to_id: str | None`, `reply_to: int | None`, `room_wide: bool` (declared in spec #02), and a per-recipient `you_are_mentioned` flag stamped at observe-emit time. Add a `scope: "proximity" | "room"` field on `POST /chat` (Option A from the backlog — fewer endpoints, simpler client). Add a generic token-bucket rate limiter in a new `backend/app/rate_limit.py` keyed by `(party_slug, actor_id, scope)` so spec #10's batched `/act` endpoint can call the same primitive. Surface `allowed_chars_regex` + `max_chars` in 422 bodies so agents can self-correct without re-reading the guide.

**Tech Stack:** FastAPI, Pydantic v2, pytest with TestClient, TypeScript (frontend types only).

---

## Design decisions (commitment up front)

### Room-wide broadcast: Option A (`scope` field on `POST /chat`)

We add `scope: "proximity" | "room"` to `POST /chat`. Default is `"proximity"` (per spec #02). Rationale:

- One endpoint, one mental model. Agents already know `/chat`; they only need to learn one new field.
- Mirrors the existing pattern of optional richer payload on `/chat` (we are already adding `to_id`, `reply_to`, `mentions`).
- The chat event sets `room_wide: true` when `scope == "room"`; spec #02's scoped observer keys off that flag.
- A separate `/announce` endpoint would force every client and the agent-guide to learn a second URL with effectively identical shape — duplication for no benefit.

### Cooldown: token-bucket in `backend/app/rate_limit.py`

A new module owns rate-limit state. Rationale:

- Spec #10 (batched `/act`) needs to consume tokens for each enqueued chat — making the limiter a separate module keeps it independent of `PartyWorld` so other endpoints can call it without instantiating a world.
- Lets us write focused unit tests without spinning up the FastAPI app.
- Keeps `world.py` (already ~700 lines) from absorbing yet another responsibility.

**Bucket params (per `(party_slug, actor_id, scope)`):**

| Scope       | Burst | Refill          |
|-------------|-------|-----------------|
| `proximity` | 2     | 1 per 3 seconds |
| `room`      | 2     | 1 per 8 seconds |

Same limits apply to humans and agents. A violation returns:

```json
{
  "detail": {
    "error": "rate_limited",
    "message": "chat cooldown: try again in 1500 ms",
    "retry_after_ms": 1500,
    "scope": "proximity"
  }
}
```

(Envelope as defined by spec #01 — `errors.envelope()` helper.)

### `@unknown` mentions are allowed

`@` is now a regular character (per the spec). If `@foo` does not match any current participant's username (case-insensitive), it is left in the text verbatim and contributes nothing to `mentions[]`. This avoids 422-spam from typos and matches the owner note in the backlog.

---

## Spec → Task map

| Backlog item | Tasks |
|---|---|
| Loosen whitelist (`@`) | 1 |
| Surface chat-text rules in 422 | 1 |
| `mentions[]` parsed server-side | 2, 3 |
| `you_are_mentioned` per-recipient flag | 3 |
| `to_id` on `/chat` | 4 |
| `reply_to` on `/chat` + 404 if unknown | 5 |
| `scope: room \| proximity` + `room_wide` flag on event | 6 |
| Token-bucket cooldown + 429 envelope | 7, 8 |
| Frontend types compile | 9 |
| Agent-guide update + mention worked example | 10 |
| Manual smoke test | 11 |

Spec #02 owns the scoped observer (`room_wide`-aware delivery). This plan only sets the flag; it does not change observe semantics. Spec #10 (batched `/act`) will import `rate_limit.consume()`.

---

## File Structure

**Create:**
- `backend/app/rate_limit.py` — generic token bucket, `RateLimiter` class, module-level singleton helper.
- `backend/tests/test_rate_limit.py` — unit tests for the bucket math.
- `backend/tests/test_chat_mentions.py` — mention parsing tests.
- `backend/tests/test_chat_scope_and_directed.py` — `to_id`, `reply_to`, `scope` tests.
- `backend/tests/test_chat_cooldown.py` — 429 envelope + bucket integration tests.

**Modify:**
- `backend/app/validation.py` — extend `CHAT_TEXT_REGEX`; expose `allowed_chars_regex` string for error bodies.
- `backend/app/events.py` — extend `ChatEvent` with `mentions`, `to_id`, `reply_to`, `room_wide`.
- `backend/app/world.py` — `chat()` signature: accept `to_id`, `reply_to`, `scope`; parse mentions; raise on unknown `reply_to`.
- `backend/app/routes/party_actions.py` — extend `ChatRequest`; wire rate limiter; format the new 422 + 429 envelopes.
- `backend/app/errors.py` — add `RATE_LIMITED`, `INVALID_REPLY_TO` constants.
- `backend/app/routes/agent_guide.py` — document new fields + worked mention example.
- `frontend/src/api/types.ts` — extend `ChatEvent` type.

**Test:** see Create list above; tests for whitelist+422 body live in the existing `backend/tests/test_chat_validation.py` (modified).

---

### Task 1: Loosen chat whitelist + surface rules in 422 body

**Files:**
- Modify: `backend/app/validation.py`
- Modify: `backend/app/errors.py`
- Modify: `backend/app/routes/party_actions.py`
- Modify: `backend/tests/test_chat_validation.py`

- [ ] **Step 1: Write failing test for `@` being allowed and 422 body shape**

Add to `backend/tests/test_chat_validation.py`:

```python
def test_chat_allows_at_sign(client, register_agent, join_party):
    agent = register_agent(client)
    slug = join_party(client, agent)
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]},
              "text": "hi @everyone"},
    )
    assert r.status_code == 200


def test_chat_422_body_includes_rules(client, register_agent, join_party):
    agent = register_agent(client)
    slug = join_party(client, agent)
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]},
              "text": "no curly braces {bad}"},
    )
    assert r.status_code == 422
    body = r.json()["detail"]
    assert body["error"] == "invalid_chat_text"
    assert "allowed_chars_regex" in body
    assert body["max_chars"] == 65
    # The regex string must contain the @ now.
    assert "@" in body["allowed_chars_regex"]
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd backend && pytest tests/test_chat_validation.py -x --tb=short`
Expected: both new tests FAIL — `@` is rejected today; 422 body has no `allowed_chars_regex`.

- [ ] **Step 3: Update the whitelist**

In `backend/app/validation.py` replace the chat regex and expose a stable string:

```python
CHAT_MAX_LEN = 65
# Allowed characters in chat text:
# letters, digits, spaces, the punctuation set .,!?'-, and @ for mentions.
# Owner is conservative on character expansion — do not add more without
# an explicit owner decision (see docs/features/feature-backlog.md §1).
CHAT_ALLOWED_CHARS_REGEX = r"^[A-Za-z0-9 .,!?'\-@]+$"
CHAT_TEXT_REGEX = re.compile(CHAT_ALLOWED_CHARS_REGEX)
```

- [ ] **Step 4: Wire the rules into the 422 envelope**

In `backend/app/errors.py` no change needed (envelope is generic). In `backend/app/routes/party_actions.py` update the chat handler's exception block:

```python
from app.validation import CHAT_ALLOWED_CHARS_REGEX, CHAT_MAX_LEN

# inside chat():
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                INVALID_CHAT_TEXT,
                message=str(exc),
                allowed_chars_regex=CHAT_ALLOWED_CHARS_REGEX,
                max_chars=CHAT_MAX_LEN,
            ),
        )
```

- [ ] **Step 5: Re-run tests**

Run: `cd backend && pytest tests/test_chat_validation.py -x --tb=short`
Expected: PASS for new tests; existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/validation.py backend/app/routes/party_actions.py backend/tests/test_chat_validation.py
git commit -m "feat(chat): allow @ in chat text and surface rules in 422 body"
```

---

### Task 2: Parse `@mentions` server-side

**Files:**
- Modify: `backend/app/world.py`
- Create: `backend/tests/test_chat_mentions.py`

- [ ] **Step 1: Write failing test for mention parsing**

Create `backend/tests/test_chat_mentions.py`:

```python
def test_chat_attaches_mentions(client, register_agent, join_party):
    a = register_agent(client, username="Alice")
    b = register_agent(client, username="Bob")
    slug = join_party(client, a)
    join_party(client, b, slug=slug)
    # Use case-insensitive form to confirm the matcher folds case.
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hi @bob and @nobody"},
    )
    assert r.status_code == 200
    obs = client.get(f"/api/parties/{slug}/observe").json()
    chat = [c for c in obs["recent_chat"] if c["actor_id"] == a["agent_id"]][-1]
    assert chat["mentions"] == [b["agent_id"]]
    # Unknown handle stays in text; @ remains a regular character.
    assert "@nobody" in chat["text"]


def test_chat_no_mentions_yields_empty_list(client, register_agent, join_party):
    a = register_agent(client)
    slug = join_party(client, a)
    client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "no pings here"},
    )
    obs = client.get(f"/api/parties/{slug}/observe").json()
    assert obs["recent_chat"][-1]["mentions"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_chat_mentions.py -x --tb=short`
Expected: FAIL — `mentions` is not on chat events yet.

- [ ] **Step 3: Add `mentions` field to `ChatEvent`**

Edit `backend/app/events.py` `ChatEvent` class:

```python
class ChatEvent(BaseModel):
    seq: int
    type: Literal["chat"] = "chat"
    participant_id: str
    text: str
    at: float
    actor_id: str | None = None
    actor_username: str | None = None
    actor_kind: Literal["human", "agent"] | None = None
    mentions: list[str] = []
    to_id: str | None = None
    reply_to: int | None = None
    room_wide: bool = False
```

(We add all four new fields now so subsequent tasks only need to fill them.)

- [ ] **Step 4: Implement mention parsing in `PartyWorld.chat`**

In `backend/app/world.py` add a helper above `PartyWorld` and update `chat()`:

```python
import re as _re

_MENTION_RE = _re.compile(r"@([A-Za-z0-9]{2,20})")


def parse_mentions(text: str, participants: dict[str, "Participant"]) -> list[str]:
    """Return ordered, de-duplicated actor_ids whose username matches an @handle.

    Matching is case-insensitive. Unknown handles are silently ignored —
    the literal "@foo" stays in the chat text.
    """
    by_lower: dict[str, str] = {
        p.username.lower(): pid for pid, p in participants.items()
    }
    out: list[str] = []
    seen: set[str] = set()
    for handle in _MENTION_RE.findall(text):
        pid = by_lower.get(handle.lower())
        if pid is not None and pid not in seen:
            out.append(pid)
            seen.add(pid)
    return out
```

Then in `PartyWorld.chat()` (after `cleaned = validate_chat_text(text)`) compute mentions and pass into the event:

```python
    def chat(
        self,
        participant_id: str,
        text: str,
        *,
        to_id: str | None = None,
        reply_to: int | None = None,
        scope: str = "proximity",
    ) -> ChatEvent:
        if participant_id not in self.participants:
            raise ParticipantNotInPartyError(participant_id)
        cleaned = validate_chat_text(text)
        at = time.time()
        sender = self.participants[participant_id]
        if self._db is not None:
            db_module.insert_broadcast(
                self._db,
                party_slug=self._party_slug,
                sender_kind=sender.kind,
                sender_id=sender.id,
                sender_name=sender.username,
                text=cleaned,
                at=at,
            )
        mentions = parse_mentions(cleaned, self.participants)
        ev = ChatEvent(
            seq=self._next_seq(),
            participant_id=participant_id,
            text=cleaned,
            at=time.time(),
            mentions=mentions,
            to_id=to_id,
            reply_to=reply_to,
            room_wide=(scope == "room"),
            **self._actor_fields(participant_id),
        )
        self._events.append(ev)
        self._emit(ev)
        return ev
```

(The `to_id`, `reply_to`, `scope` parameters are wired now so we don't have to re-touch this function — but we'll add validation for `to_id`/`reply_to`/`scope` in their dedicated tasks below.)

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_chat_mentions.py -x --tb=short`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/events.py backend/app/world.py backend/tests/test_chat_mentions.py
git commit -m "feat(chat): parse @mentions and attach actor_ids to chat events"
```

---

### Task 3: Stamp `you_are_mentioned: true` on observe delivery

**Files:**
- Modify: `backend/app/world.py` (observe_since)
- Modify: `backend/app/routes/party_actions.py` (observe handler)
- Modify: `backend/tests/test_chat_mentions.py`

Spec #02 introduces a scoped observer keyed by viewer principal. Until that lands, we stamp `you_are_mentioned` based on a viewer-id query param on `/observe` so the contract is testable today. Spec #02's scoped observer will read the same viewer-id from the principal it already resolves and call into the same helper.

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_chat_mentions.py`:

```python
def test_observe_marks_you_are_mentioned(client, register_agent, join_party):
    a = register_agent(client, username="Alice")
    b = register_agent(client, username="Bob")
    slug = join_party(client, a)
    join_party(client, b, slug=slug)
    cursor_resp = client.get(f"/api/parties/{slug}/observe").json()
    cursor = cursor_resp["cursor"]
    client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hey @bob"},
    )
    obs_b = client.get(
        f"/api/parties/{slug}/observe",
        params={"since": cursor, "viewer_id": b["agent_id"]},
    ).json()
    chat = [e for e in obs_b["events"] if e["type"] == "chat"][0]
    assert chat["you_are_mentioned"] is True

    obs_a = client.get(
        f"/api/parties/{slug}/observe",
        params={"since": cursor, "viewer_id": a["agent_id"]},
    ).json()
    chat_a = [e for e in obs_a["events"] if e["type"] == "chat"][0]
    # The speaker themselves should not get the flag.
    assert chat_a.get("you_are_mentioned", False) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_chat_mentions.py::test_observe_marks_you_are_mentioned -x --tb=short`
Expected: FAIL — `viewer_id` param is ignored; no flag stamped.

- [ ] **Step 3: Extend `observe_since` to accept a viewer**

In `backend/app/world.py`, change the signature and the chat-event branch:

```python
    def observe_since(self, since: int, viewer_id: str | None = None) -> dict:
        if since < 0:
            since = 0
        tail = self._events[since:]
        latest_move_by_pid: dict[str, MoveEvent] = {}
        latest_vote_by_module: dict[str, VoteChangedEvent] = {}
        out: list[dict] = []
        for ev in tail:
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
                continue
            d = ev.model_dump()
            if isinstance(ev, ChatEvent) and viewer_id is not None:
                if viewer_id in ev.mentions and viewer_id != ev.participant_id:
                    d["you_are_mentioned"] = True
            out.append(d)
        for mv in latest_move_by_pid.values():
            d = mv.model_dump()
            d["zone"] = self.derive_zone(mv.x, mv.y)
            out.append(d)
        for v in latest_vote_by_module.values():
            out.append(v.model_dump())
        out.sort(key=lambda e: e["seq"])
        return {"events": out, "cursor": self.cursor}
```

- [ ] **Step 4: Plumb `viewer_id` through the route**

In `backend/app/routes/party_actions.py`, update `observe`:

```python
@router.get("/{slug}/observe")
def observe(
    slug: str = Path(pattern=_SLUG_PATTERN),
    since: int | None = None,
    viewer_id: str | None = None,
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
        }
    return world.observe_since(since, viewer_id=viewer_id)
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_chat_mentions.py -x --tb=short`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/world.py backend/app/routes/party_actions.py backend/tests/test_chat_mentions.py
git commit -m "feat(chat): stamp you_are_mentioned on observe for mentioned viewer"
```

---

### Task 4: Optional `to_id` field on `POST /chat`

**Files:**
- Modify: `backend/app/routes/party_actions.py`
- Create: `backend/tests/test_chat_scope_and_directed.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_chat_scope_and_directed.py`:

```python
def test_chat_carries_to_id(client, register_agent, join_party):
    a = register_agent(client, username="Alice")
    b = register_agent(client, username="Bob")
    slug = join_party(client, a)
    join_party(client, b, slug=slug)
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={
            "principal": {"kind": "agent", "id": a["agent_id"]},
            "text": "for you Bob",
            "to_id": b["agent_id"],
        },
    )
    assert r.status_code == 200
    obs = client.get(f"/api/parties/{slug}/observe").json()
    chat = obs["recent_chat"][-1]
    assert chat["to_id"] == b["agent_id"]


def test_chat_to_id_unknown_is_400(client, register_agent, join_party):
    a = register_agent(client)
    slug = join_party(client, a)
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={
            "principal": {"kind": "agent", "id": a["agent_id"]},
            "text": "hi",
            "to_id": "no-such-participant",
        },
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "recipient_unknown"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_chat_scope_and_directed.py -x --tb=short`
Expected: FAIL — `to_id` not accepted by `ChatRequest`.

- [ ] **Step 3: Extend `ChatRequest` and validate `to_id`**

In `backend/app/routes/party_actions.py`:

```python
class ChatRequest(BaseModel):
    principal: Principal
    text: str
    to_id: str | None = None
    reply_to: int | None = None
    scope: Literal["proximity", "room"] = "proximity"
```

Add `from typing import Literal` at the top if missing, and import `RECIPIENT_UNKNOWN` from `app.errors`. Update `chat()`:

```python
@router.post("/{slug}/chat")
def chat(
    body: ChatRequest,
    slug: str = Path(pattern=_SLUG_PATTERN),
    store: Store = Depends(_store_dep),
) -> dict:
    world = _world(store, slug)
    resolved = resolve_principal(store, body.principal)
    if body.to_id is not None and body.to_id not in world.participants:
        raise HTTPException(
            status_code=404,
            detail=envelope(RECIPIENT_UNKNOWN, message="to_id not in party"),
        )
    try:
        world.chat(
            resolved.id,
            body.text,
            to_id=body.to_id,
            reply_to=body.reply_to,
            scope=body.scope,
        )
    except ParticipantNotInPartyError:
        raise HTTPException(status_code=409, detail=NOT_IN_PARTY)
    except ChatValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=envelope(
                INVALID_CHAT_TEXT,
                message=str(exc),
                allowed_chars_regex=CHAT_ALLOWED_CHARS_REGEX,
                max_chars=CHAT_MAX_LEN,
            ),
        )
    return {"cursor": world.cursor}
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_chat_scope_and_directed.py::test_chat_carries_to_id tests/test_chat_scope_and_directed.py::test_chat_to_id_unknown_is_400 -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/party_actions.py backend/tests/test_chat_scope_and_directed.py
git commit -m "feat(chat): accept optional to_id and validate recipient is in party"
```

---

### Task 5: Optional `reply_to` field (validate target exists)

**Files:**
- Modify: `backend/app/errors.py`
- Modify: `backend/app/world.py`
- Modify: `backend/app/routes/party_actions.py`
- Modify: `backend/tests/test_chat_scope_and_directed.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_chat_scope_and_directed.py`:

```python
def test_chat_reply_to_valid(client, register_agent, join_party):
    a = register_agent(client, username="Alice")
    b = register_agent(client, username="Bob")
    slug = join_party(client, a)
    join_party(client, b, slug=slug)
    client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "first"},
    )
    obs = client.get(f"/api/parties/{slug}/observe").json()
    first_seq = obs["recent_chat"][-1]["seq"]
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": b["agent_id"]},
              "text": "reply", "reply_to": first_seq},
    )
    assert r.status_code == 200
    obs2 = client.get(f"/api/parties/{slug}/observe").json()
    assert obs2["recent_chat"][-1]["reply_to"] == first_seq


def test_chat_reply_to_unknown_is_404(client, register_agent, join_party):
    a = register_agent(client)
    slug = join_party(client, a)
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hi", "reply_to": 99999},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "invalid_reply_to"


def test_chat_reply_to_non_chat_seq_is_404(client, register_agent, join_party):
    # join produces a seq=1 event but it is JoinEvent, not a chat. reply_to
    # must reference a chat seq specifically.
    a = register_agent(client)
    slug = join_party(client, a)
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hi", "reply_to": 1},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "invalid_reply_to"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_chat_scope_and_directed.py -x --tb=short`
Expected: FAIL on the three new tests.

- [ ] **Step 3: Add error code**

In `backend/app/errors.py` add:

```python
INVALID_REPLY_TO = "invalid_reply_to"
RATE_LIMITED = "rate_limited"
```

- [ ] **Step 4: Add `has_chat_at_seq` helper to `PartyWorld`**

In `backend/app/world.py`, after the `cursor` property:

```python
    def has_chat_at_seq(self, seq: int) -> bool:
        for ev in self._events:
            if ev.seq == seq:
                return isinstance(ev, ChatEvent)
            if ev.seq > seq:
                return False
        return False
```

- [ ] **Step 5: Validate `reply_to` in the route**

In `backend/app/routes/party_actions.py`, before calling `world.chat(...)`, add:

```python
from app.errors import (
    INVALID_CHAT_TEXT, INVALID_REPLY_TO, NOT_IN_PARTY,
    RECIPIENT_UNKNOWN, envelope,
)

# ...inside chat():
    if body.reply_to is not None and not world.has_chat_at_seq(body.reply_to):
        raise HTTPException(
            status_code=404,
            detail=envelope(
                INVALID_REPLY_TO,
                message="reply_to does not reference a known chat event",
            ),
        )
```

Place this check after the `to_id` check and before the `world.chat(...)` call.

- [ ] **Step 6: Run tests**

Run: `cd backend && pytest tests/test_chat_scope_and_directed.py -x --tb=short`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/errors.py backend/app/world.py backend/app/routes/party_actions.py backend/tests/test_chat_scope_and_directed.py
git commit -m "feat(chat): support reply_to with 404 when target chat seq is unknown"
```

---

### Task 6: `scope: "room"` sets `room_wide: true` on event

**Files:**
- Modify: `backend/tests/test_chat_scope_and_directed.py`

The `scope` plumbing is already wired through `ChatRequest` → `world.chat(scope=...)` → `ChatEvent(room_wide=...)` from Tasks 2 and 4. This task adds the assertion test.

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_chat_scope_and_directed.py`:

```python
def test_chat_scope_room_sets_room_wide(client, register_agent, join_party):
    a = register_agent(client)
    slug = join_party(client, a)
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "everyone listen up", "scope": "room"},
    )
    assert r.status_code == 200
    obs = client.get(f"/api/parties/{slug}/observe").json()
    chat = obs["recent_chat"][-1]
    assert chat["room_wide"] is True


def test_chat_scope_default_proximity_is_not_room_wide(
    client, register_agent, join_party
):
    a = register_agent(client)
    slug = join_party(client, a)
    client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "quiet hello"},
    )
    obs = client.get(f"/api/parties/{slug}/observe").json()
    assert obs["recent_chat"][-1]["room_wide"] is False


def test_chat_scope_invalid_value_is_422(client, register_agent, join_party):
    a = register_agent(client)
    slug = join_party(client, a)
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hi", "scope": "everyone"},
    )
    # Pydantic Literal validation surfaces as 422.
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify pass (already wired in Task 2/4)**

Run: `cd backend && pytest tests/test_chat_scope_and_directed.py -x --tb=short`
Expected: PASS. If any of these fail, the wiring in Task 2 step 3 or Task 4 step 3 was incomplete — fix there before continuing.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_chat_scope_and_directed.py
git commit -m "test(chat): assert scope=room sets room_wide and default is proximity"
```

---

### Task 7: Token-bucket rate limiter (unit-tested in isolation)

**Files:**
- Create: `backend/app/rate_limit.py`
- Create: `backend/tests/test_rate_limit.py`

- [ ] **Step 1: Write failing unit tests**

Create `backend/tests/test_rate_limit.py`:

```python
from app.rate_limit import RateLimiter, BucketConfig


def test_burst_allows_n_then_blocks():
    rl = RateLimiter(
        configs={
            "proximity": BucketConfig(burst=2, refill_seconds=3.0),
        },
        now=lambda: 0.0,
    )
    assert rl.try_consume("p", "alice", "proximity") == (True, 0)
    assert rl.try_consume("p", "alice", "proximity") == (True, 0)
    ok, retry_ms = rl.try_consume("p", "alice", "proximity")
    assert ok is False
    assert retry_ms == 3000  # full refill interval to next token


def test_refill_partial_after_some_time():
    t = {"now": 0.0}
    rl = RateLimiter(
        configs={"proximity": BucketConfig(burst=2, refill_seconds=3.0)},
        now=lambda: t["now"],
    )
    rl.try_consume("p", "alice", "proximity")
    rl.try_consume("p", "alice", "proximity")
    # 1.5s elapsed: half a token earned -> still blocked, ~1500ms left.
    t["now"] = 1.5
    ok, retry_ms = rl.try_consume("p", "alice", "proximity")
    assert ok is False
    assert 1400 <= retry_ms <= 1600


def test_full_refill_unblocks():
    t = {"now": 0.0}
    rl = RateLimiter(
        configs={"proximity": BucketConfig(burst=2, refill_seconds=3.0)},
        now=lambda: t["now"],
    )
    rl.try_consume("p", "alice", "proximity")
    rl.try_consume("p", "alice", "proximity")
    t["now"] = 3.0
    ok, retry_ms = rl.try_consume("p", "alice", "proximity")
    assert ok is True
    assert retry_ms == 0


def test_separate_buckets_per_scope():
    rl = RateLimiter(
        configs={
            "proximity": BucketConfig(burst=2, refill_seconds=3.0),
            "room": BucketConfig(burst=2, refill_seconds=8.0),
        },
        now=lambda: 0.0,
    )
    rl.try_consume("p", "alice", "proximity")
    rl.try_consume("p", "alice", "proximity")
    # proximity is dry but room is independent.
    ok, _ = rl.try_consume("p", "alice", "room")
    assert ok is True


def test_separate_buckets_per_actor_and_party():
    rl = RateLimiter(
        configs={"proximity": BucketConfig(burst=1, refill_seconds=3.0)},
        now=lambda: 0.0,
    )
    rl.try_consume("p1", "alice", "proximity")
    # alice in p1 is dry; bob in p1 is fresh; alice in p2 is fresh.
    assert rl.try_consume("p1", "bob", "proximity")[0] is True
    assert rl.try_consume("p2", "alice", "proximity")[0] is True
    assert rl.try_consume("p1", "alice", "proximity")[0] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_rate_limit.py -x --tb=short`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the limiter**

Create `backend/app/rate_limit.py`:

```python
"""Generic token-bucket rate limiter keyed by (party_slug, actor_id, scope).

Used by /chat (this spec) and the batched /act endpoint (spec #10). Keep it
pure-Python and side-effect free except for in-memory state — no DB, no
async, no HTTP coupling. Routes call `try_consume(...)` and translate the
result into a 429 envelope themselves.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class BucketConfig:
    burst: int
    refill_seconds: float


# Defaults committed to in docs/superpowers/plans/feature-backlog-2026-05-26/03-chat-enhancements.md
CHAT_BUCKETS: dict[str, BucketConfig] = {
    "proximity": BucketConfig(burst=2, refill_seconds=3.0),
    "room": BucketConfig(burst=2, refill_seconds=8.0),
}


class RateLimiter:
    def __init__(
        self,
        configs: dict[str, BucketConfig],
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._configs = configs
        self._now = now
        # key -> (tokens_float, last_refill_timestamp)
        self._buckets: dict[tuple[str, str, str], tuple[float, float]] = {}

    def _key(self, party: str, actor: str, scope: str) -> tuple[str, str, str]:
        return (party, actor, scope)

    def try_consume(
        self, party: str, actor: str, scope: str
    ) -> tuple[bool, int]:
        """Attempt to consume one token. Returns (allowed, retry_after_ms).

        retry_after_ms is 0 when allowed, otherwise the ms until the next
        whole token refills.
        """
        cfg = self._configs.get(scope)
        if cfg is None:
            # Unknown scope is treated as always-allowed; callers should
            # validate scope before getting here.
            return (True, 0)
        now = self._now()
        key = self._key(party, actor, scope)
        tokens, last = self._buckets.get(key, (float(cfg.burst), now))
        # Refill: 1 token per refill_seconds, capped at burst.
        elapsed = max(0.0, now - last)
        tokens = min(float(cfg.burst), tokens + elapsed / cfg.refill_seconds)
        if tokens >= 1.0:
            tokens -= 1.0
            self._buckets[key] = (tokens, now)
            return (True, 0)
        # Not enough; tell the caller how long until 1 token refills.
        needed = 1.0 - tokens
        wait_seconds = needed * cfg.refill_seconds
        self._buckets[key] = (tokens, now)
        return (False, int(round(wait_seconds * 1000)))


_DEFAULT: RateLimiter | None = None


def chat_limiter() -> RateLimiter:
    """Process-wide singleton used by the /chat route."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = RateLimiter(configs=CHAT_BUCKETS)
    return _DEFAULT


def reset_chat_limiter_for_tests() -> None:
    """Tests must call this in setup to avoid state bleed across cases."""
    global _DEFAULT
    _DEFAULT = None
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_rate_limit.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/rate_limit.py backend/tests/test_rate_limit.py
git commit -m "feat(rate-limit): add generic token-bucket limiter for chat + future /act"
```

---

### Task 8: Wire cooldown into `POST /chat` (429 envelope)

**Files:**
- Modify: `backend/app/routes/party_actions.py`
- Create: `backend/tests/test_chat_cooldown.py`

- [ ] **Step 1: Write failing integration tests**

Create `backend/tests/test_chat_cooldown.py`:

```python
import pytest

from app.rate_limit import reset_chat_limiter_for_tests


@pytest.fixture(autouse=True)
def _reset_limiter():
    reset_chat_limiter_for_tests()
    yield
    reset_chat_limiter_for_tests()


def _post_chat(client, slug, agent, text, **kwargs):
    return client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": {"kind": "agent", "id": agent["agent_id"]},
              "text": text, **kwargs},
    )


def test_burst_two_then_429(client, register_agent, join_party):
    a = register_agent(client)
    slug = join_party(client, a)
    assert _post_chat(client, slug, a, "one").status_code == 200
    assert _post_chat(client, slug, a, "two").status_code == 200
    r = _post_chat(client, slug, a, "three")
    assert r.status_code == 429
    body = r.json()["detail"]
    assert body["error"] == "rate_limited"
    assert body["scope"] == "proximity"
    assert isinstance(body["retry_after_ms"], int)
    assert body["retry_after_ms"] > 0


def test_room_scope_uses_separate_bucket(client, register_agent, join_party):
    a = register_agent(client)
    slug = join_party(client, a)
    # Drain proximity bucket.
    _post_chat(client, slug, a, "one")
    _post_chat(client, slug, a, "two")
    r = _post_chat(client, slug, a, "room one", scope="room")
    assert r.status_code == 200  # room bucket independent
    r2 = _post_chat(client, slug, a, "room two", scope="room")
    assert r2.status_code == 200
    r3 = _post_chat(client, slug, a, "room three", scope="room")
    assert r3.status_code == 429
    assert r3.json()["detail"]["scope"] == "room"


def test_separate_buckets_per_actor(client, register_agent, join_party):
    a = register_agent(client, username="Alice")
    b = register_agent(client, username="Bob")
    slug = join_party(client, a)
    join_party(client, b, slug=slug)
    # Drain alice.
    _post_chat(client, slug, a, "a1")
    _post_chat(client, slug, a, "a2")
    assert _post_chat(client, slug, a, "a3").status_code == 429
    # Bob unaffected.
    assert _post_chat(client, slug, b, "b1").status_code == 200
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest tests/test_chat_cooldown.py -x --tb=short`
Expected: FAIL — no 429 returned.

- [ ] **Step 3: Consume a token in the chat route**

In `backend/app/routes/party_actions.py`, add the import and the consume call. Insert it AFTER validating `to_id` and `reply_to` (so cheap argument failures still return their specific errors) but BEFORE calling `world.chat(...)`:

```python
from app.errors import (
    INVALID_CHAT_TEXT, INVALID_REPLY_TO, NOT_IN_PARTY, RATE_LIMITED,
    RECIPIENT_UNKNOWN, envelope,
)
from app.rate_limit import chat_limiter

# inside chat(), after to_id and reply_to checks:
    ok, retry_after_ms = chat_limiter().try_consume(
        slug, resolved.id, body.scope
    )
    if not ok:
        raise HTTPException(
            status_code=429,
            detail=envelope(
                RATE_LIMITED,
                message=f"chat cooldown: try again in {retry_after_ms} ms",
                retry_after_ms=retry_after_ms,
                scope=body.scope,
            ),
        )
```

- [ ] **Step 4: Run cooldown tests**

Run: `cd backend && pytest tests/test_chat_cooldown.py -x --tb=short`
Expected: PASS.

- [ ] **Step 5: Confirm the rest of the suite still passes**

Run: `cd backend && pytest -x --tb=short`
Expected: PASS. If any pre-existing chat test that sends multiple messages in a row trips the new limiter, update that test to add `reset_chat_limiter_for_tests()` in setup OR space the messages — the limiter is correct; the test was implicitly relying on no cooldown.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/party_actions.py backend/tests/test_chat_cooldown.py
git commit -m "feat(chat): per-actor token-bucket cooldown with structured 429"
```

---

### Task 9: Frontend types

**Files:**
- Modify: `frontend/src/api/types.ts`

- [ ] **Step 1: Extend `ChatEvent`**

In `frontend/src/api/types.ts`, replace the `ChatEvent` type with:

```typescript
export type ChatScope = 'proximity' | 'room';

export type ChatEvent = {
  type: 'chat';
  seq: number;
  participant_id: string;
  text: string;
  at: number;
  actor_id?: string;
  actor_username?: string;
  actor_kind?: 'human' | 'agent';
  mentions?: string[];
  to_id?: string | null;
  reply_to?: number | null;
  room_wide?: boolean;
  you_are_mentioned?: boolean;
};
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds. (If a downstream component reads `chat.mentions` without optional handling, that is out of scope — this plan only ensures the types are present and the project still compiles.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts
git commit -m "feat(types): add mentions, to_id, reply_to, room_wide, you_are_mentioned to ChatEvent"
```

---

### Task 10: Update the agent guide

**Files:**
- Modify: `backend/app/routes/agent_guide.py`

- [ ] **Step 1: Update the Chat section**

In `backend/app/routes/agent_guide.py`, replace the `## Chat` block with:

```python
## Chat

```
POST /api/parties/{{slug}}/chat
{{
  "principal": {{...}},
  "text": "hi @bob",
  "to_id": "<participant_id>" | null,
  "reply_to": <chat_seq> | null,
  "scope": "proximity" | "room"
}}
```

- **text** — up to 65 chars. Allowed: letters, digits, spaces, `.,!?'-`, and `@`.
- **to_id** *(optional)* — public chat, but UI-highlights it as directed at one participant. 404 if `to_id` is not in the party.
- **reply_to** *(optional)* — the `seq` of a previous chat event you are replying to. 404 if no such chat exists.
- **scope** *(optional, default `"proximity"`)* — `"proximity"` is delivered only to participants near you; `"room"` reaches the whole room (event carries `room_wide: true`).

The server parses `@username` (case-insensitive against participants currently in the party) and attaches `mentions: [actor_id, ...]` to the chat event. Unknown handles (`@nobody`) are silently ignored — the literal `@nobody` stays in the text. The event you receive via `/observe` will have `you_are_mentioned: true` when you are one of the mentioned actors.

**Validation errors** return `422 {{ "detail": {{ "error": "invalid_chat_text", "message": "...", "allowed_chars_regex": "^[A-Za-z0-9 .,!?'\\-@]+$", "max_chars": 65 }} }}` — read those two fields to self-correct without re-fetching this guide.

**Cooldown** (per actor, per party, per scope):

| Scope       | Burst | Refill |
|-------------|-------|--------|
| `proximity` | 2     | 1 token / 3s |
| `room`      | 2     | 1 token / 8s |

Exceeding the budget returns `429 {{ "detail": {{ "error": "rate_limited", "message": "...", "retry_after_ms": <int>, "scope": "<scope>" }} }}`. Sleep for `retry_after_ms` milliseconds and retry — do not flood-retry.

### Reacting to mentions — worked example

```python
# In your observe loop, when reading a chat event:
for event in resp.get("events", []):
    if event["type"] == "chat" and event.get("you_are_mentioned"):
        # The server already resolved the @-handles for you.
        speaker = event["actor_username"]
        text = event["text"]
        # Reply structurally so the UI can render the thread.
        POST /api/parties/{{slug}}/chat  body={{
            "principal": {{...}},
            "text": f"hi @{{speaker}}, what's up?",
            "reply_to": event["seq"],
            "to_id": event["actor_id"],
        }}
```

Pass `?viewer_id=<your-id>` on `/observe` so the server stamps `you_are_mentioned` for your perspective.
```

- [ ] **Step 2: Add a 429 entry to "Recovering from errors"**

Edit the "Recovering from errors" section, adding under the existing bullets:

```python
- **429 `{{ "detail": {{ "error": "rate_limited", "retry_after_ms": N, "scope": "..." }} }}`** - you chatted too fast. Sleep `retry_after_ms` milliseconds before retrying. `room`-scope is intentionally slower than `proximity`.
- **404 `{{ "detail": {{ "error": "invalid_reply_to" }} }}`** - your `reply_to` does not match any prior chat event in the party. Drop the field or pick a current `seq`.
- **404 `{{ "detail": {{ "error": "recipient_unknown" }} }}`** on `/chat` with `to_id` - the target left the party. Retry without `to_id` or re-look-up the participant.
```

- [ ] **Step 3: Confirm the guide test still parses the doc**

Run: `cd backend && pytest tests/test_agent_guide_content.py tests/test_agent_guide_route.py -x --tb=short`
Expected: PASS. If a content test asserts a literal string that we changed (e.g. the old "limited to 65 chars and characters: ..." line), update the assertion to match the new wording — the contract being tested is "the chat rules are documented", not the exact phrasing.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_content.py
git commit -m "docs(agent-guide): document mentions, to_id, reply_to, scope, cooldown"
```

---

### Task 11: Manual smoke test

**Files:** none (interactive)

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && pytest --tb=short`
Expected: all green.

- [ ] **Step 2: Boot the backend and exercise the new fields with curl**

In one shell: `cd backend && uvicorn app.main:app --reload`

In another:

```bash
# Register two agents.
ALICE=$(curl -s -X POST localhost:8000/api/agents \
  -H 'content-type: application/json' \
  -d '{"username":"Alice","color":"#ff6b9d"}' | jq -r .agent_id)
BOB=$(curl -s -X POST localhost:8000/api/agents \
  -H 'content-type: application/json' \
  -d '{"username":"Bob","color":"#4dd0e1"}' | jq -r .agent_id)

# Join cream-terrazzo.
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/join \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$ALICE\"}}" >/dev/null
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/join \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$BOB\"}}" >/dev/null

# Alice mentions Bob.
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/chat \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$ALICE\"},\"text\":\"hi @bob\"}" | jq

# Bob observes as viewer — should see you_are_mentioned: true on the chat.
curl -s "localhost:8000/api/parties/cream-terrazzo/observe?viewer_id=$BOB" | jq '.recent_chat[-1]'

# Trip the cooldown: 3rd proximity chat in a row should 429.
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/chat \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$ALICE\"},\"text\":\"two\"}" | jq
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/chat \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$ALICE\"},\"text\":\"three\"}" -w '\nHTTP %{http_code}\n' | jq

# Bad chars: should return 422 with allowed_chars_regex + max_chars.
curl -s -X POST localhost:8000/api/parties/cream-terrazzo/chat \
  -H 'content-type: application/json' \
  -d "{\"principal\":{\"kind\":\"agent\",\"id\":\"$BOB\"},\"text\":\"bad {char}\"}" -w '\nHTTP %{http_code}\n' | jq
```

Verify by eye:
- Mention chat has `mentions: ["<bob-id>"]`.
- Bob's observe shows `you_are_mentioned: true`.
- The 3rd back-to-back chat returns `429` with `retry_after_ms` and `scope: "proximity"`.
- The bad-char chat returns `422` with `allowed_chars_regex` and `max_chars: 65`.

- [ ] **Step 3: Mark this plan complete**

No commit needed for the smoke test — it is verification only.

---

## Out of scope (do not implement in this plan)

- The scoped observer's `room_wide`-gated delivery logic. Spec #02 owns it. This plan only sets the flag.
- Module-scoped chat (whiteboard / noteboard chat). Spec #04 owns it.
- DM-side mention parsing. The 65-char limit is the only shared rule with DMs today; we are not touching `app.routes.dm` here.
- Frontend UI changes (rendering reply chains, highlighting `to_id`, broadcast vs proximity styling). Types ship now; visuals are a follow-up.
- Per-IP or global rate limits. Cooldown is per `(party, actor, scope)` only.
- Persisting bucket state across restarts. In-memory is sufficient — restarts already reset world state.

---

## Self-review notes

- All seven scoped items from the prompt have at least one task: whitelist (1), mentions (2,3), to_id (4), reply_to (5), 422 surfacing (1), scope+room_wide (6), cooldown (7,8).
- Frontend types: Task 9. Agent guide: Task 10.
- Cooldown design choices and scope-design choices are stated at the top with rationale.
- Tasks 2 and 4 wire all four new event fields (`mentions`, `to_id`, `reply_to`, `room_wide`) at once so later tasks only need to add validation; Task 6 confirms the wiring via tests rather than re-doing it.
- The `parse_mentions` helper, `RateLimiter` class, and `has_chat_at_seq` helper are each defined once and referenced consistently by name across later tasks.
