# Phase 5 — Speech Bubbles (Broadcast Chat in the Room)

**Date:** 2026-05-13
**Status:** Draft
**Branch:** TBD (`feat/phase5-speech-bubbles` suggested)

## Problem

Broadcast chat already exists on the backend: `POST /api/parties/{slug}/chat` creates a `ChatEvent`, the realtime hub fans it out to every party WS subscriber. But the frontend doesn't render chat events and there's no input. So humans at a party today see avatars move and join/leave — never speak.

Phase 5 makes broadcast chat visible. No DMs, no persistence, no scrollback. Messages appear as ephemeral speech bubbles above the speaker's avatar and disappear after a few seconds.

## Decisions (from brainstorm)

- **Chat scope:** broadcast to everyone in the party. (DMs come in Phase 6.)
- **Surface:** speech bubbles only — no persistent chat panel in the room.
- **History:** none in Phase 5 (scrollback is a Phase 6 thing, and only for DMs).
- **Persistence:** none in Phase 5. Bubbles live and die in memory.

## Architecture

```
ChatInput ──POST /api/parties/{slug}/chat──▶ party_actions.chat
                                                    │
                                              world.chat() emits ChatEvent
                                                    │
                                              PartyHub fan-out
                                                    │
                                              ws frame {type:"event", event:{type:"chat", participant_id, text, at, seq}}
                                                    │
                                              useRealtimeParty receives ─▶ bubbles map
                                                                              │
                                                                       ChatBubble (5s lifetime, fades last 500ms)
                                                                       positioned above matching avatar
```

All the backend pieces already exist. The only backend change is verifying the WS chat frame includes the fields the frontend reads (`participant_id`, `text`, `at`, `seq`); add them if missing.

## Components

**Backend**

- `backend/app/realtime.py` — verify `_serialise_event` for `ChatEvent` exposes `participant_id` and `text`. Add a test that asserts the frame shape. No new module.

**Frontend**

- `frontend/src/hooks/useRealtimeParty.ts` — extend the `event` handler with a `chat` branch. Add a `bubbles: Map<participantId, { text, expiresAt }>` to the hook's state alongside `participants`. New chat from a participant replaces their existing entry. `leave` events prune the entry. The hook exposes `bubbles` to consumers.
- `frontend/src/components/ChatBubble.tsx` — small absolutely-positioned bubble. Accepts `x`, `y`, `text`, `expiresAt`. Schedules its own removal via `setTimeout`; CSS fade in the last 500ms. Clamps within the room rect.
- `frontend/src/components/ChatInput.tsx` — pinned to the bottom of the party view. Single-line `<input>` with Enter to send. Client-side validation reuses the same regex/length constraint as the server (mirror constants in a shared `frontend/src/api/validation.ts`). Disabled when realtime status ≠ `open`. Calls existing `chatInParty()`.
- `frontend/src/components/PartySpace.tsx` — render `<ChatBubble>` for each entry in `bubbles`, looking up the current `(x, y)` of the matching participant so the bubble follows the avatar while alive. Mount `<ChatInput>` inside the party view container.

## Data Flow

1. User types `"hi"` in `ChatInput`, hits Enter.
2. Client-side validation passes; `chatInParty(slug, principal, "hi")` POSTs.
3. Server validates, calls `world.chat()`, emits `ChatEvent` with `participant_id = sender`.
4. `PartyHub` serialises and broadcasts the frame to every party subscriber (including sender — UI re-renders from server state, no optimistic insert).
5. `useRealtimeParty.onmessage` adds `{ text: "hi", expiresAt: now + 5000 }` to `bubbles[sender_id]`.
6. `PartySpace` renders `<ChatBubble>` anchored to sender's avatar.
7. After 5s, the bubble removes itself; the next render drops it from `bubbles`.

## Validation & Errors

- Text validation: shared regex (`CHAT_TEXT_REGEX`) and max length (280) on both sides. Server already enforces; client mirrors to give instant feedback.
- Empty / too long / disallowed chars: client refuses to POST, shows inline error under the input.
- WS closed: input is disabled (visually greyed) with title attribute "Reconnecting…". No queueing.
- Bubble for a participant who has left mid-flight: pruned on `leave` event.
- Two bubbles overlapping spatially: acceptable in Phase 5; we don't attempt collision avoidance for chat bubbles.

## Testing

**Backend**
- One pytest asserting `_serialise_event` for `ChatEvent` produces the keys the frontend reads.

**Frontend**
- `useRealtimeParty.test.ts` — adds tests for: chat event inserts bubble; consecutive chats from the same participant replace; `leave` prunes; bubble expiry is time-based (`vi.useFakeTimers`).
- `ChatBubble.test.tsx` — renders text, auto-removes after timer.
- `ChatInput.test.tsx` — validates input client-side, calls `chatInParty` on Enter, clears on success, disabled when status closed.
- `PartySpace.test.tsx` — renders one bubble per active entry, positions it over the matching participant.

## Files Affected

- `backend/app/realtime.py` (maybe; verify only)
- `backend/tests/test_realtime.py` (new test)
- `frontend/src/api/validation.ts` (new — shared constants)
- `frontend/src/hooks/useRealtimeParty.ts` (extend)
- `frontend/src/components/ChatBubble.tsx` (new)
- `frontend/src/components/ChatInput.tsx` (new)
- `frontend/src/components/PartySpace.tsx` (mount input, render bubbles)
- Matching `tests/` files for each new component/hook update

## Out of Scope (defer to Phase 6)

- Any persistence of chat (broadcast scrollback, DMs, SQLite).
- DM threads / DM UI / inbox / proximity gate.
- Notifications, unread counts, sounds.
- Bubble collision avoidance, rich-text/markdown, emoji picker, image attachments.
- Rate-limiting (broadcast chat could become noisy; revisit after DMs land).
