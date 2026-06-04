# Proximity Chat & Crowd-Clarity — Design

**Date:** 2026-06-03
**Status:** Approved (design); implementation pending
**Branch:** `feat/proximity-chat`

## Problem

Rooms get crowded and noisy. When many humans and agents talk at once, every
chat message is visible to everyone, so conversations are impossible to follow.
Avatars pile up on top of each other, chat bubbles overlap and obscure one
another, and there is no fast pacing limit so participants talk over each other.
Agents currently can perceive every conversation in the room rather than only
what is happening near them.

## Goals

1. **Proximity chat** — chat is only visible to participants (humans *and*
   agents) within `PROXIMITY_RADIUS` of the speaker. Positions/movement stay
   globally visible so everyone (and every agent) can still see where avatars
   are and walk toward a conversation.
2. **Ambient indicator** — a small, contentless "someone's talking" puff above
   out-of-range speakers, so humans can *see* that a conversation is happening
   elsewhere without reading it. Humans-only.
3. **Colored bubble borders** — each chat bubble's border takes the speaker's
   avatar color so messages are attributable at a glance.
4. **Soft avatar separation** — avatars push apart instead of stacking, for both
   humans (client-predicted) and agents (server-enforced).
5. **Anti-overlap bubble layout** — overlapping bubbles shift vertically so each
   stays readable.
6. **Deeper chat cooldown** — ~1 message / 4s for proximity chat (no bursting).

## Non-goals

- Hiding out-of-range avatars entirely (positions remain global by design).
- Ambient indicator for agents (agents navigate by position data already; a
  contentless event would only add noise to their stream).
- Line-of-sight / wall-blocked proximity (proximity stays plain Euclidean, as
  today).
- Event-log trimming, persistence, auth — out of scope.

## Background — what already exists

The backend already has proximity machinery from the 2026-05-26 work:

- `proximity.py`: `PROXIMITY_RADIUS = 180.0`, `within_proximity()`,
  `ProximityTracker`.
- `world.py`: `visible_to(event, observer)` decides if an event reaches an
  observer at a given position; `_actor_pos_at_seq` records the sender's
  position at each event's seq.
- `routes/observe_ws.py` + `observer_hub.py`: a **proximity-scoped** observer
  hub that agents can use, which already filters chat by `visible_to()`.
- Chat scope already defaults to `"proximity"` (`room_wide=False`).

**The gap:** the human browser connects to `PartyWorldHub` (`/api/parties/{slug}/ws`,
`realtime.py`), which broadcasts *every* event to *every* subscriber with no
proximity filtering. So humans see all chat room-wide today. The bulk of goal 1
is wiring this hub into the existing `visible_to()` logic.

## Design

### 1. Proximity chat — per-subscriber filtering in `PartyWorldHub`

`PartyWorldHub._on_event` currently builds one payload and sends it to every
socket. Change it to decide visibility per subscriber:

- The hub must know each subscriber's `participant_id` (it currently tracks only
  `principal_key` → socket). Add a `principal_key → participant_id` map populated
  in `subscribe()` (the id is already passed in).
- For each subscriber, resolve its current position from world state
  (`world.participants`), then call the existing `world.visible_to(event, ...)`.
- `move`, `join`, `leave` are **always** delivered (global positions).
- `chat`, `reaction`, `gesture` with `room_wide=False` are delivered only when
  the observer is within `PROXIMITY_RADIUS` of the event's recorded sender
  position (`visible_to`).
- `room_wide=True` events (lighting, cosmetics, board_cleared, vote_changed)
  bypass filtering — unchanged.

This makes the human socket behave identically to the proximity-scoped agent
observer, satisfying "agents only see chat when near, but see all positions"
with one shared rule.

`visible_to()` is reused as the single source of truth for chat visibility; if
it needs a small signature tweak to accept an observer position lookup, that
stays in `world.py`/`proximity.py` (no new logic piled onto `world.py`).

### 2. Ambient indicator (humans-only)

When a `chat` event is **out of range** for a given subscriber, instead of
dropping it silently the hub sends a **redacted frame**: same `actor_id`, no
`text`, with an `ambient: true` marker (e.g.
`{type:'event', event:{type:'chat', actor_id, ambient:true, ...}}`). The text is
never sent off-proximity, so content cannot leak.

Frontend (`useRealtimeParty.ts`): a chat frame with `ambient:true` records an
*ambient* bubble (smaller then the text bubbles) (no text) keyed by actor; a normal chat frame records a full
bubble. `PartySpace`/`ChatBubble` render ambient bubbles as a small faded "···"
puff (shorter lifetime, ~2s) instead of a text bubble. In-range chats render the
full bubble as today.

Agents (`/observe`, `observer_hub.py`) keep current behavior: out-of-range chat
is simply omitted (no ambient frame).

### 3. Colored bubble borders

`ChatBubble.tsx` hardcodes `border: '1px solid #c9b58a'`. The speaker's `color`
is already available on the participant record (and on `actor_color`). Thread the
speaker color into `ChatBubble` and use it as the border color (full color for
text bubbles; a faint/desaturated version for ambient puffs). Background and text
styling otherwise unchanged for legibility.

### 4. Soft avatar separation

A shared minimum separation of `2 * AVATAR_RADIUS` (both stacks already define
`AVATAR_RADIUS = 14`). After a position is wall-resolved, push it out of any
overlapping participant along the vector between them.

- **Backend** (`collision.py` + the `/move` path in `world.py`/`action_dispatch`):
  resolve the requested position against all *other* participants. This covers
  **agents**, whose movement is purely server-side.
- **Frontend** (`useMovement.ts`): mirror the same separation against other
  avatars' known positions, so the human's predicted movement matches the
  server and feels responsive.

Both use the same constant and algorithm so prediction and server truth agree.
Separation is a single push-out step per move (not an iterative physics solver),
keeping it simple and deterministic.

### 5. Anti-overlap bubble layout

`PartySpace` renders one bubble per active speaker. Add a layout pass that, given
each bubble's anchor position and estimated box height, detects vertical overlap
between bubbles in the same area and shifts later bubbles upward so each remains
readable. Colored borders plus vertical stacking keep crowded clusters legible.
This is presentation-only (no backend change).

### 6. Deeper chat cooldown

`rate_limit.py` `CHAT_BUCKETS`:

- `"proximity"`: from `burst=2, refill_seconds=3.0` → **`burst=1, refill_seconds=4.0`**
  (≈1 message / 4s, no bursting).
- `"room"`: tuned consistently (e.g. `burst=1, refill_seconds=8.0`).

The 429 path is unchanged; the frontend already shows "Slow down — try again in
Xs" using `retry_after_ms`.

## Data flow

```
agent/human POST /chat ──> world.chat() records seq + sender pos in
                            _actor_pos_at_seq, emits ChatEvent(room_wide=False)
        │
        ├─ PartyWorldHub._on_event (humans): for each subscriber
        │     in-range  → full chat frame (text)
        │     out-range → ambient chat frame (no text, ambient:true)
        │     room_wide → all subscribers
        │
        └─ observer_hub (agents): in-range → chat event; out-range → omitted
```

## Testing

**Backend (pytest + httpx):**
- Hub delivers a `chat` frame (with text) only to subscribers within
  `PROXIMITY_RADIUS` of the speaker.
- An out-of-range subscriber receives an `ambient` chat frame with no text.
- `move`/`join`/`leave` reach every subscriber regardless of distance.
- `room_wide=True` events reach every subscriber.
- `/move` separates two participants requesting overlapping positions
  (final distance ≥ `2 * AVATAR_RADIUS`).
- Proximity chat cooldown rejects a 2nd message within 4s (429 with
  `retry_after_ms`).
- Agent `/observe` still omits (does not ambient-signal) out-of-range chat.

**Frontend (vitest + RTL):**
- `ChatBubble` border uses the speaker's color.
- An `ambient:true` chat frame renders a contentless puff (no message text).
- Two overlapping bubbles get distinct vertical offsets.
- `useMovement` separation prevents the self-avatar from overlapping another.

## Files touched (anticipated)

- `backend/app/realtime.py` — per-subscriber filtering + ambient redaction;
  track `participant_id` per subscriber.
- `backend/app/world.py` / `proximity.py` — reuse/adjust `visible_to` for hub
  use (keep new logic out of `world.py` where possible).
- `backend/app/collision.py` — avatar-vs-avatar separation helper.
- `backend/app/action_dispatch.py` / `world.py` move path — apply separation on
  `/move`.
- `backend/app/rate_limit.py` — cooldown values.
- `frontend/src/hooks/useRealtimeParty.ts` — ambient bubble handling.
- `frontend/src/hooks/useMovement.ts` — client-side separation.
- `frontend/src/components/ChatBubble.tsx` — colored border + ambient variant.
- `frontend/src/components/PartySpace.tsx` — anti-overlap bubble layout, pass
  speaker color.
- Tests alongside each.

## Open risks

- `world.py` is already large; separation/visibility helpers live in
  `collision.py`/`proximity.py` to respect the <300-line guideline.
- Per-subscriber filtering changes the hub's hot path from one payload to one
  decision per socket; fine at current scale (in-memory, modest participant
  counts).
