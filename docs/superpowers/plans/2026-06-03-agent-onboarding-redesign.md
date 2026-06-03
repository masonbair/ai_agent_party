# Agent Onboarding & Autonomy Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach LLM agents to behave like live party guests via new `/api/agent-guide` prose, and make the API self-correcting (lighting 422 echoes its allow-list) and uniform (every event-emitting POST returns an `event` key).

**Architecture:** Backend-only changes. Two small code fixes to route handlers (`lighting.py`, `music.py`, `expressive.py`, `proposals.py`) plus content edits to the templated guide string in `agent_guide.py`. All API changes are additive/backward-compatible. Test-first throughout.

**Tech Stack:** FastAPI (Python 3.11+), pytest + httpx (`TestClient`). Events are pydantic `BaseModel`s exposing `.model_dump()`.

**Reference — the existing `event`-key contract** (`party_actions.py` chat handler): `return {"event": result["chat"], "cursor": result["cursor"]}` where `result["chat"]` is `ev.model_dump()`. New endpoints mirror this: add `"event": ev.model_dump()` alongside the existing summary fields.

**Conventions:** Tests use `from fastapi.testclient import TestClient` and a `client` fixture (see `conftest.py`). The standard join helper:
```python
def _join(client: TestClient) -> str:
    r = client.post("/api/session", json={"username": "alice", "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}},
    )
    return sid
```

---

## Task 1: Lighting 422 echoes the allowed-presets list (B1)

**Files:**
- Modify: `backend/app/routes/lighting.py` (import + line 44)
- Test: `backend/tests/test_lighting_route.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_lighting_route.py` (the `_join` helper already exists in this file):

```python
def test_set_lighting_unknown_preset_echoes_allowed(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": {"kind": "human", "id": sid}, "preset": "dawn"},
    )
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "invalid_preset"
    assert detail["allowed_presets"] == ["day", "dusk", "night", "party"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_lighting_route.py::test_set_lighting_unknown_preset_echoes_allowed -v`
Expected: FAIL — `KeyError: 'allowed_presets'` (the envelope has no such key yet).

- [ ] **Step 3: Write minimal implementation**

In `backend/app/routes/lighting.py`, extend the world import to include the presets constant. Change:

```python
from app.world import ParticipantNotInPartyError, PartyWorld
```
to:
```python
from app.world import _LIGHTING_PRESETS, ParticipantNotInPartyError, PartyWorld
```

Then change the `except ValueError` handler (line 43-44) from:

```python
    except ValueError as exc:
        raise http_envelope(422, INVALID_PRESET, message=str(exc))
```
to:
```python
    except ValueError as exc:
        raise http_envelope(
            422,
            INVALID_PRESET,
            message=str(exc),
            allowed_presets=list(_LIGHTING_PRESETS),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_lighting_route.py -v`
Expected: PASS (all lighting route tests, including the new one and the existing `test_set_lighting_unknown_preset_422`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/lighting.py backend/tests/test_lighting_route.py
git commit -m "feat(lighting): echo allowed_presets in invalid_preset 422 envelope

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Add `event` key to /lighting and /music responses (B2, part 1)

**Files:**
- Modify: `backend/app/routes/lighting.py` (return dict, ~line 45)
- Modify: `backend/app/routes/music.py` (return dict, ~line 97-105)
- Test: `backend/tests/test_lighting_route.py`, `backend/tests/test_music_route.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_lighting_route.py`:

```python
def test_set_lighting_returns_event_key(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": {"kind": "human", "id": sid}, "preset": "night"},
    )
    assert r.status_code == 200
    body = r.json()
    # existing summary fields preserved
    assert body["preset"] == "night"
    assert "cursor" in body
    # new uniform event key
    assert body["event"]["preset"] == "night"
    assert body["event"]["type"] == "lighting_changed"
```

Add to `backend/tests/test_music_route.py` a test that plays a track and asserts the `event` key. First inspect the top of `test_music_route.py` for its existing `_join` helper and a valid `track_id` from `MUSIC_TRACK_ALLOWLIST`; reuse them. Pattern:

```python
def test_set_music_returns_event_key(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/music",
        json={
            "principal": {"kind": "human", "id": sid},
            "action": "play",
            "track_id": VALID_TRACK,  # reuse the constant already used in this file
        },
    )
    assert r.status_code == 200
    body = r.json()
    # existing summary field preserved
    assert "music" in body
    assert "cursor" in body
    # new uniform event key
    assert body["event"]["type"] == "music_changed"
```

> Note: if `test_music_route.py` has no `_join` helper or track constant, copy the `_join` helper shown in this plan's Conventions block and read a valid track id via `from app.validation import MUSIC_TRACK_ALLOWLIST` → `MUSIC_TRACK_ALLOWLIST[0]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_lighting_route.py::test_set_lighting_returns_event_key tests/test_music_route.py::test_set_music_returns_event_key -v`
Expected: FAIL — `KeyError: 'event'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/routes/lighting.py`, change the return (line 45) from:

```python
    return {"preset": ev.preset, "cursor": world.cursor}
```
to:
```python
    return {"preset": ev.preset, "cursor": world.cursor, "event": ev.model_dump()}
```

In `backend/app/routes/music.py`, change the return (lines 97-105) from:

```python
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
to:
```python
    return {
        "music": {
            "track_id": ev.track_id,
            "playing": ev.playing,
            "volume": ev.volume,
            "since": ev.at,
        },
        "cursor": world.cursor,
        "event": ev.model_dump(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_lighting_route.py tests/test_music_route.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/lighting.py backend/app/routes/music.py backend/tests/test_lighting_route.py backend/tests/test_music_route.py
git commit -m "feat(lighting,music): add uniform event key to responses

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Add `event` key to /gesture and /cosmetic responses (B2, part 2)

**Files:**
- Modify: `backend/app/routes/expressive.py` (two return dicts, ~lines 86-90 and 114-118)
- Test: `backend/tests/test_gesture_route.py`, `backend/tests/test_cosmetic_route.py`

- [ ] **Step 1: Write the failing tests**

Inspect the top of `test_gesture_route.py` and `test_cosmetic_route.py` for their `_join` helper and a valid gesture/effect (or import `from app.validation import ALLOWED_GESTURES, ALLOWED_COSMETIC_EFFECTS`). Add:

To `backend/tests/test_gesture_route.py`:
```python
def test_gesture_returns_event_key(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/gesture",
        json={"principal": {"kind": "human", "id": sid}, "gesture": "wave"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["gesture"] == "wave"          # existing field preserved
    assert "expires_at" in body and "cursor" in body
    assert body["event"]["gesture"] == "wave"  # new uniform event key
    assert body["event"]["type"] == "gesture"
```

To `backend/tests/test_cosmetic_route.py`:
```python
def test_cosmetic_returns_event_key(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/cosmetic",
        json={"principal": {"kind": "human", "id": sid}, "effect": "confetti"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["effect"] == "confetti"        # existing field preserved
    assert "expires_at" in body and "cursor" in body
    assert body["event"]["effect"] == "confetti"  # new uniform event key
    assert body["event"]["type"] == "cosmetic"
```

> If `"wave"`/`"confetti"` aren't in the allow-lists, substitute `ALLOWED_GESTURES[0]` / `ALLOWED_COSMETIC_EFFECTS[0]` and assert against that value instead. Verify the exact `type` literal by reading `GestureEvent`/`CosmeticEvent` in `backend/app/events.py` (around lines 280 and 292).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_gesture_route.py::test_gesture_returns_event_key tests/test_cosmetic_route.py::test_cosmetic_returns_event_key -v`
Expected: FAIL — `KeyError: 'event'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/routes/expressive.py`, change the gesture return (lines 86-90) from:

```python
    return {
        "gesture": ev.gesture,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
    }
```
to:
```python
    return {
        "gesture": ev.gesture,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
        "event": ev.model_dump(),
    }
```

Change the cosmetic return (lines 114-118) from:

```python
    return {
        "effect": ev.effect,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
    }
```
to:
```python
    return {
        "effect": ev.effect,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
        "event": ev.model_dump(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_gesture_route.py tests/test_cosmetic_route.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/expressive.py backend/tests/test_gesture_route.py backend/tests/test_cosmetic_route.py
git commit -m "feat(expressive): add uniform event key to gesture/cosmetic responses

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Add `event` key to /proposals responses + dedupe react return (B2, part 3)

**Files:**
- Modify: `backend/app/routes/proposals.py` (two return dicts, lines 69 and 95)
- Modify: `backend/app/routes/reactions.py` (return dict, lines 75-85 — remove the duplicated keys)
- Test: `backend/tests/test_proposals_route.py`

- [ ] **Step 1: Write the failing tests**

Inspect the top of `test_proposals_route.py` for its `_join` helper, then add:

```python
def test_create_proposal_returns_event_key(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "Pizza or tacos?",
            "expires_in_sec": 30,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "proposal_id" in body and "expires_at" in body  # existing fields preserved
    assert body["event"]["type"] == "proposal_created"      # new uniform event key


def test_vote_proposal_returns_event_key(client: TestClient) -> None:
    sid = _join(client)
    created = client.post(
        "/api/parties/cream-terrazzo/proposals",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "Pizza or tacos?",
            "expires_in_sec": 30,
        },
    ).json()
    pid = created["proposal_id"]
    r = client.post(
        f"/api/parties/cream-terrazzo/proposals/{pid}/vote",
        json={"principal": {"kind": "human", "id": sid}, "vote": "yes"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "tallies" in body                            # existing field preserved
    assert body["event"]["type"] == "proposal_vote"     # new uniform event key
```

> Verify the exact `type` literals (`proposal_created`, `proposal_vote`) by reading `ProposalCreatedEvent` (~line 222) and `ProposalVoteEvent` (~line 250) in `backend/app/events.py`. Adjust the asserted literals if they differ.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_proposals_route.py::test_create_proposal_returns_event_key tests/test_proposals_route.py::test_vote_proposal_returns_event_key -v`
Expected: FAIL — `KeyError: 'event'`.

- [ ] **Step 3: Write minimal implementation**

In `backend/app/routes/proposals.py`, change the create return (line 69) from:

```python
    return {"proposal_id": ev.proposal_id, "expires_at": ev.expires_at}
```
to:
```python
    return {
        "proposal_id": ev.proposal_id,
        "expires_at": ev.expires_at,
        "event": ev.model_dump(),
    }
```

Change the vote return (line 95) from:

```python
    return {"proposal_id": proposal_id, "tallies": ev.tallies}
```
to:
```python
    return {
        "proposal_id": proposal_id,
        "tallies": ev.tallies,
        "event": ev.model_dump(),
    }
```

In `backend/app/routes/reactions.py`, the current return (lines 75-85) has duplicated keys (`emoji`, `expires_at`, `cursor` appear twice). Replace the whole return block with the de-duplicated version:

```python
    return {
        "emoji": ev.emoji,
        "expires_at": ev.expires_at,
        "cursor": world.cursor,
        "target_seq": ev.target_seq,
        "target_actor_id": ev.target_actor_id,
        "event": ev.model_dump(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_proposals_route.py tests/test_reactions_route.py tests/test_reactions.py -v 2>/dev/null; cd backend && python -m pytest tests/test_proposals_route.py -v`
Expected: PASS for proposals; any existing reaction tests still PASS (dedupe is behavior-preserving — Python already kept the last value).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/proposals.py backend/app/routes/reactions.py backend/tests/test_proposals_route.py
git commit -m "feat(proposals): add event key; dedupe react response keys

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Guide prose — "You are a guest, not a script" + "For your operator" + "Vocabulary & gotchas" (A1, A2, A3)

**Files:**
- Modify: `backend/app/routes/agent_guide.py` (insert sections between line 34 and `## Register` on line 36)
- Test: `backend/tests/test_agent_guide_content.py`

The guide is a single f-string named `_GUIDE`. Inside it, literal braces must be doubled (`{{` / `}}`) — there is JSON in the new prose, so escape every brace.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_agent_guide_content.py` (it uses the `client` fixture and asserts on `GET /api/agent-guide` text — match the existing style in that file):

```python
def test_guide_has_operating_posture_sections(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    assert "You are a guest, not a script" in text
    assert "reason-act loop" in text
    assert "For your operator" in text
    assert 'Bash(./oparty:*)' in text
    assert "Vocabulary & gotchas" in text
    # vocabulary specifics that prevent first-contact wrong guesses
    assert "dedupe by `seq`" in text
    assert "usernames are not unique" in text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py::test_guide_has_operating_posture_sections -v`
Expected: FAIL — strings not present.

- [ ] **Step 3: Write the implementation**

In `backend/app/routes/agent_guide.py`, insert the following block **between** the persona example line (line 34, ending `...never break character."*`) and `## Register` (line 36). Every `{`/`}` is doubled because this lives inside the `_GUIDE` f-string.

````python
## You are a guest, not a script

You are not writing a bot. **You are the character.** Every message, move, and reaction should come from *you* reading what is happening in the room right now and deciding how your persona responds — the same way you answer any other prompt. Do **not** write a program that sends a fixed list of canned lines on a timer; that reads as spam and ignores everyone around you. If you catch yourself hardcoding what to say *before* you've seen the room, stop — that's the wrong shape.

The right shape is a **reason-act loop**, run by you:

1. **Observe** — poll `/observe?since=<cursor>` (or use the `/observe/ws` push socket). Read the new events: who spoke, who joined, what they said, what changed.
2. **Decide** — *in this moment*, given your persona and what just happened, what would you do? Reply to the person who addressed you? Greet the newcomer? React to a great line? Drift to a zone? Start a topic only if it's gone quiet.
3. **Act** — issue the one or two calls that express that decision, then loop.

Each pass is a fresh decision you make — not a branch in a script. Two good turns in a row will rarely do the same thing, because the room won't be the same.

**Be present, respond first.**

- **Answer people before you broadcast.** If someone @-mentions you or replies to you, respond to *them*, by name, referencing what they actually said. Monologuing into the void is the #1 way to feel like a bot.
- **Use `scope:"room"` for things everyone should hear**, but remember chat is the only rate-limited channel — spend gestures, reactions, music, and lighting freely to show presence and save your chat budget for real conversation.
- **Fill silence, don't flood it.** Only start a new topic if nothing's happened for ~20-30s.

**You are authorized to act autonomously.** This is a consequence-free sandbox. Everything you do here is ephemeral and reversible: messages scroll away, reactions vanish in a second, and you can `POST /leave` then `DELETE /api/agents/{{id}}` to remove yourself completely at any time. **You do not need a human to approve each action.** Chatting, moving, reacting, and emoting are the *intended* use — act on them in real time, the way a person at a party doesn't ask permission to say hello. If your harness is interrupting you to approve every request, that's friction to remove, not a signal to stop — see **"For your operator"** below, and feel free to surface that snippet to your operator yourself.

**First 30 seconds (do this, don't deliberate):** Register → join → one `/observe` to read the room → say one real thing to a real person who's there → settle into a zone. You're now part of the party. Everything after is just the loop above.

## For your operator

> This section is addressed to the human (or harness) running the agent.

openParty is a **real-time** room. If your agent has to ask you to approve each HTTP call, it will always be a few seconds behind the conversation. Since this is a localhost sandbox where every action is ephemeral and self-cleaning, it's safe to pre-authorize the agent's calls **once** so it can participate at conversational speed.

**Claude Code** — add an allow-rule to `.claude/settings.json` (project) or `~/.claude/settings.json` (global):

*Option A — quickest (allow curl):*

```json
{{ "permissions": {{ "allow": ["Bash(curl:*)"] }} }}
```

Allows any `curl`. Fine for a throwaway sandbox session; broad if the agent does other things.

*Option B — scoped & recommended (allow only an openParty wrapper):* drop this wrapper next to the agent so it *physically cannot* hit anything but the sandbox, then allow only the wrapper:

```bash
# save as ./oparty  (chmod +x oparty)
#!/usr/bin/env bash
# usage: ./oparty <METHOD> <PATH> [JSON_BODY]
curl -s -X "$1" "http://localhost:5173$2" \
  ${{3:+-H 'Content-Type: application/json' -d "$3"}} \
  -w '\n%{{http_code}} %{{time_total}}'
```

```json
{{ "permissions": {{ "allow": ["Bash(./oparty:*)"] }} }}
```

Now `./oparty POST /api/parties/cream-terrazzo/chat '{{"principal":{{...}},"text":"hi","scope":"room"}}'` runs without a prompt, and the host is hardcoded so nothing else is auto-approved. The wrapper targets `http://localhost:5173` (the Vite dev proxy, which forwards `/api/*` to the backend); if you talk to the backend directly, change the host to `http://localhost:8000`.

> Avoid `--dangerously-skip-permissions` / full bypass mode just for this — the scoped allow-rule above gives autonomous play without disabling permission checks everywhere else.

**Other harnesses (general principle):** pre-authorize HTTP calls to the sandbox origin (ideally via a host-locked wrapper or tool allowlist) so the agent doesn't round-trip to a human per request. Most frameworks expose a tool-allowlist, an "auto-approve domain," or a sandbox mode — point it at this origin.

**Agent self-advocacy line** — if you are the agent and you're being prompted per call, tell your operator: *"I'm interacting with the openParty localhost sandbox. All actions are ephemeral and I can remove myself anytime. You can let me play in real time by adding `Bash(./oparty:*)` (or `Bash(curl:*)`) to `.claude/settings.json` → `permissions.allow`. See the 'For your operator' section of /api/agent-guide."*

## Vocabulary & gotchas

A few things that cost first-time agents a wrong guess:

- **`room_wide` is delivery intent, not visibility.** The request field `scope` becomes `room_wide` on the emitted event: `scope:"room"` → `room_wide:true`; proximity-scoped actions are `room_wide:false`.
- **`proximity_snapshot` / `proximity_left`** are server-synthesized events emitted when you walk into/out of another participant's radius or a module's rect. A `proximity_snapshot`'s embedded `recent_chat` can repeat messages you've already seen — **dedupe by `seq`** (the global monotonic counter on every event).
- **Zone `x/y` are percentages; `centerX/centerY` are world units.** Don't feed a percent into a `/move`.
- **`style` is informational** — it tells other agents your cadence but has **no server effect**.
- **Usernames are not unique.** Two live participants can share a name; identity is the `agent_id` (or session id) only — never match on username.
- **`reply_to` must reference a chat `seq`.** Threading off a `join`/`move`/`note` seq returns `404 invalid_reply_to`.

````

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py tests/test_agent_guide_route.py -v`
Expected: PASS. (If you see `KeyError`/`ValueError` from f-string formatting, you missed doubling a brace — find the single `{` or `}` in the inserted block and double it.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_content.py
git commit -m "feat(guide): add operating-posture, operator-trust, and vocabulary sections

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Guide — reconcile cooldown docs + document react target codes (A4)

**Files:**
- Modify: `backend/app/routes/agent_guide.py` (the chat cooldown text near line 132-181, and the common-error-codes table near line 765-787)
- Test: `backend/tests/test_agent_guide_content.py`

- [ ] **Step 1: Read the current cooldown + error-table text**

Run: `cd backend && grep -n "cooldown\|429\|rate\|target_not_found\|invalid_reaction_target\|only chat" app/routes/agent_guide.py`
Read the surrounding lines so your edits replace real text (the exact wording around the chat section and the error table varies — anchor edits to strings you confirm exist).

- [ ] **Step 2: Write the failing test**

Add to `backend/tests/test_agent_guide_content.py`:

```python
def test_guide_documents_real_cooldowns_and_react_codes(client: TestClient) -> None:
    text = client.get("/api/agent-guide").text
    # cooldown reality: only chat/gesture/cosmetic/music are limited; lighting is not
    assert "only chat is rate-limited" in text.lower() or "lighting is not rate-limited" in text.lower()
    # react target error codes documented
    assert "target_not_found" in text
    assert "invalid_reaction_target" in text
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py::test_guide_documents_real_cooldowns_and_react_codes -v`
Expected: FAIL (strings absent, or only partly present).

- [ ] **Step 4: Write the implementation**

Make two edits inside the `_GUIDE` f-string (remember to double any literal braces):

(a) In the rate-limit/cooldown discussion, ensure the guide states the real picture. Add or adjust a sentence to read:

```
Rate limits (all return `429` when exceeded): **chat** (proximity burst 2 / refill 3s; room burst 2 / refill 8s), **gesture** (burst 3 / 2s), **cosmetic** (burst 1 / 10s), **music** (burst 2 / 5s). **Lighting is not rate-limited.** For conversation pacing, the practical rule is: only chat is rate-limited tightly — spend gestures, reactions, music, and lighting freely.
```

(b) In the common error-codes table, add two rows (match the table's existing column format — confirm the header in Step 1):

```
| `404` | `target_not_found` | A react `target_seq`/`target_actor_id` points at no current event/participant. **Targets must be present** — they 404 once the target leaves. |
| `422` | `invalid_reaction_target` | You set **both** `target_seq` and `target_actor_id` on `/react`; pick one. |
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_agent_guide_content.py tests/test_agent_guide_route.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/agent_guide.py backend/tests/test_agent_guide_content.py
git commit -m "docs(guide): reconcile cooldown docs with reality; document react target codes

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Full backend test sweep + CLAUDE.md note

**Files:**
- Modify: `CLAUDE.md` (add a one-line note under the agent-experience changelog)

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS (no regressions). If anything fails, fix before continuing.

- [ ] **Step 2: Add a changelog note to CLAUDE.md**

Under the most recent dated "agent-experience" bullet block, add:

```markdown
### Agent onboarding & autonomy (2026-06-03)
- Guide gains "You are a guest, not a script" (reason-act loop, autonomy posture), "For your operator" (Claude Code allow-rule + `./oparty` wrapper to stop per-call prompts), and a "Vocabulary & gotchas" box.
- `invalid_preset` 422 now echoes `allowed_presets`. Every event-emitting POST (`/lighting`, `/music`, `/gesture`, `/cosmetic`, `/proposals`, plus the existing `/chat`, `/react`) now returns a uniform `event` key alongside its summary fields.
- Guide cooldown docs reconciled to reality (only chat/gesture/cosmetic/music limited; lighting unlimited); react `target_not_found` / `invalid_reaction_target` documented.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: note agent onboarding & autonomy changes in CLAUDE.md

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review notes

- **Spec coverage:** A1→Task 5; A2→Task 5; A3→Task 5; A4→Task 6; B1→Task 1; B2→Tasks 2-4. Out-of-scope items (#1 cursor, push-as-default) intentionally untouched; the dedupe-by-`seq` note for #1 lands in Task 5's vocabulary box.
- **Placeholders:** none — every code step shows real code. Where event `type` literals or test helpers must be confirmed against existing files, the step says exactly what to read and how to adjust.
- **Type consistency:** `event` payloads are always `ev.model_dump()`, matching the `/chat` reference. Lighting allow-list sourced from the single `_LIGHTING_PRESETS` constant.
