# Phase 4 — Multi-User Realtime Design

**Status:** Draft
**Date:** 2026-05-12
**Phase reference:** Step 4 in `CLAUDE.md` — "multi user support via websockets or some other networking tool. Should allow for multiple people and agents to interact with this page at the same time, and move around in real time."

**Depends on:** Phase 3 (`2026-05-12-phase3-agent-api-design.md`) — uses its `PartyWorld`, `Participant`, event types, and party-action endpoints (`/join`, `/leave`, `/move`, `/chat`, `/observe`).

---

## Purpose

Make the world *live*. After Phase 3, agents and humans can both join the same `PartyWorld` and read it via polling. Phase 4 does two things:

1. **Backend** — push events (`join`/`leave`/`move`/`chat`) to subscribed clients over a WebSocket, eliminating polling latency.
2. **Frontend** — render every participant in the party, not just the local user. Send movement updates to the server. React to incoming events in real time.

The WebSocket transport is **additive**. The Phase 3 `GET /observe` polling endpoint stays — agents can use whichever transport fits their loop. The frontend always uses WebSocket; agents may opt in.

---

## Architecture

### Backend

One new module + one new endpoint.

```
backend/app/
├── realtime.py            # NEW: PartyWorldHub — subscribers + broadcast
├── routes/
│   ├── parties.py         # gains: GET /api/parties/{slug}/ws (WebSocket upgrade)
│   └── ...                # untouched
├── world.py               # gains: on_event(callback) registry hook
└── ...
```

**`PartyWorldHub`** sits next to `Store`:

- One hub per party slug, created lazily when the first subscriber connects.
- Maintains a set of `WebSocket` connections per slug.
- Subscribes to its `PartyWorld`'s `on_event` callbacks.
- When the world emits an event, the hub broadcasts a JSON-serialised version to every connected socket.
- Cleans up sockets on disconnect / error.

**`PartyWorld.on_event(callback)`** — Phase 3 already records events; Phase 4 adds a *callback registry* so the hub gets notified synchronously when each event is appended. Implementation is a simple list of `Callable[[Event], None]`; `append_event` calls them after committing the event. No async required — the broadcast itself dispatches to an `asyncio.Queue` per socket so the world stays sync-friendly for tests.

**WebSocket endpoint:** `GET /api/parties/{slug}/ws`

Flow:
1. Client opens the WebSocket.
2. **First client message** is the auth/handshake frame:
   ```json
   {"type": "auth", "principal": {"kind": "human", "id": "<session_id>"}}
   ```
3. Server validates the principal exactly like the HTTP party-action endpoints (kind + id must exist in `Store`). On failure, server sends `{"type": "error", "detail": "invalid principal"}` and closes.
4. On success, server immediately sends a snapshot frame matching `/observe` no-`since` shape, with an added `"type": "snapshot"` discriminator and current cursor.
5. From then on, server pushes one frame per world event:
   ```json
   {"type": "event", "event": {<JoinEvent | LeaveEvent | MoveEvent | ChatEvent>}, "cursor": <int>}
   ```
6. Client messages after auth are **ignored** in Phase 4 — actions (move, chat, etc.) still go over HTTP. This keeps the protocol unidirectional and trivial to reason about. Phase 5+ may invert this.

**Subscription scope:** a socket is bound to one party slug, the same one whose URL it connected to. The hub for `cream-terrazzo` only sees `cream-terrazzo` events.

**Lifecycle vs `/join`:** Opening a WebSocket does **not** auto-join the principal to the party — `POST /api/parties/{slug}/join` still does that. The WS only subscribes to the *observation* stream. A principal can be subscribed without being in the party (useful for an agent that wants to "watch" before deciding to join). A principal can be joined without a WS (the polling agent case).

### Frontend

```
frontend/src/
├── hooks/
│   ├── useRealtimeParty.ts   # NEW: WS subscription + participant map
│   └── useMovement.ts        # gains: onMove callback (throttled)
├── components/
│   ├── PartySpace.tsx        # renders all participants (not just self)
│   ├── Avatar.tsx            # gains: variant prop ("self" | "other")
│   └── ...
└── api/
    └── party.ts              # NEW: thin wrappers — join, leave, move, chat
```

**`useRealtimeParty(slug, principal)`** owns one `WebSocket` and a `Map<string, Participant>` of all participants in the party. It:
- Connects to `ws(s)://<host>/api/parties/{slug}/ws`.
- Sends the auth frame.
- On `snapshot`, replaces the local map with the snapshot's participants.
- On `event`, applies the event to the local map (`join` → set, `leave` → delete, `move` → update x/y, `chat` → append to a small chat ring buffer).
- Returns `{ participants: Participant[], chatLog: ChatEvent[], status: 'connecting' | 'open' | 'closed' }`.
- Reconnects with exponential backoff on disconnect (capped at ~10s) and re-sends auth. A reconnect resets the local map via a fresh snapshot.

**`useMovement` extension** — accept an optional `onMove(x, y)` callback. Phase 1's hook already owns position state; we add a throttled emit (≤ 10 Hz, configurable) every time the local position changes. The Party page wires `onMove` to a fire-and-forget `POST /api/parties/{slug}/move`. We do **not** wait for the server's broadcast to echo our own move back — we already see ourselves locally. We *do* receive our own move events back from the server (the hub doesn't filter); the participant-map updater detects the echo (`participant_id === self.id`) and ignores it, preventing position fights.

**Multi-avatar rendering** — `PartySpace` reads `participants` from the hook, renders one `<Avatar>` per entry, and adds a `variant` prop so the local user's avatar can have a subtle indicator (e.g., a 1px white inner ring). Other avatars do not have hover or click behavior in Phase 4; that's Phase 5+.

---

## Frame schemas

All WebSocket frames are JSON, one frame per message. Discriminated by `type`.

**Server → client:**

| `type`       | Shape                                                                                                              |
|--------------|--------------------------------------------------------------------------------------------------------------------|
| `snapshot`   | `{ "type": "snapshot", "room": {…}, "participants": [Participant], "cursor": int }`                                |
| `event`      | `{ "type": "event", "event": JoinEvent ｜ LeaveEvent ｜ MoveEvent ｜ ChatEvent, "cursor": int }`                       |
| `error`      | `{ "type": "error", "detail": str }` — terminal; server closes after sending                                       |

**Client → server:**

| `type`       | Shape                                                                                                              |
|--------------|--------------------------------------------------------------------------------------------------------------------|
| `auth`       | `{ "type": "auth", "principal": { "kind": "human" ｜ "agent", "id": str } }` — first frame only                     |

Reusing the Phase 3 event types means no new pydantic models for the event payloads; only the wrapper.

---

## Move throttling & echo handling

- Frontend throttle: send `POST /move` no more than once every 100ms. If the user moves continuously, the most recent unsent position is sent on the next available tick (drop-intermediate).
- On disconnect or rapid path changes, drop pending sends — the next confirmed local position will trigger a fresh send.
- The server's `move` handler updates the world's position and emits a `MoveEvent`. The hub broadcasts to everyone, *including the sender*. The frontend's `useRealtimeParty` ignores `move` events with `participant_id === self.id` since the local position is authoritative for the local user.
- Other clients render incoming move events with a 150ms CSS transition on the avatar `<div>` (Phase 2 already does this) so apparent motion is smooth despite the 10 Hz update rate.

---

## Error handling

| Condition                                              | Behavior                                                                                |
|--------------------------------------------------------|------------------------------------------------------------------------------------------|
| Invalid principal on WS auth                           | Server sends `error` frame and closes; frontend stops retrying.                          |
| Network drop / server restart                          | Frontend reconnects with exponential backoff (1s, 2s, 4s, 8s, 8s, …); resets state on success. |
| `POST /move` returns 401/409                           | Frontend stops sending moves and surfaces an error toast; user is bounced to `/lobby`.   |
| Local position update while WS closed                  | Local-only motion still works (single-player feel); other clients won't see it until reconnect. |
| Many subscribers, slow consumer                        | Per-socket bounded queue (size 64). If full, the server drops the socket. Acceptable for v1 — we are not a streaming service. |

---

## Out of scope (deferred)

- **Voice / audio** (Step 5+).
- **Per-zone music switching** (Step 5+; Phase 1's music placeholder remains).
- **Avatar interactions** (chat bubbles on hover, click to start DM). Phase 5 will revisit; Phase 4 ships with a single shared chat log we can render in a corner panel but not over individual avatars.
- **Persistence of past chats across reconnect** beyond the in-memory ring buffer. The server's event log retains them; the client re-syncs via snapshot on reconnect.
- **Position interpolation** (sub-frame lerping between received `move` events). The 150ms CSS transition is good enough at 10 Hz; explicit interpolation can come later if we drop to <5 Hz.
- **WS scaling beyond one Python process** (sticky-session routing, Redis pub/sub fan-out). Out of scope for the demo.
- **Action frames over WebSocket** (client → server move/chat). Phase 4 keeps actions on HTTP; the protocol is forward-compatible.

---

## Testing

Strict TDD per `.ai/CONVENTIONS.md`.

### Backend unit

- `PartyWorld.on_event(callback)` registers and invokes the callback on each new event.
- `PartyWorldHub.subscribe(socket)` adds, `unsubscribe(socket)` removes; broadcast delivers to each subscribed socket; broadcast survives one slow subscriber being dropped.

### Backend WS route

Uses FastAPI's `TestClient.websocket_connect`. Each test starts with an empty `Store` via the existing fixture.

- Connect → send valid auth (human) → receive a `snapshot` frame matching the room and current participants.
- Connect with invalid principal → receive `error` frame and the socket closes.
- After a second client joins via HTTP, both sockets receive a `JoinEvent` frame.
- After one client moves via HTTP, both sockets receive a `MoveEvent` frame with the latest position. (Move collapsing happens in the polling endpoint, NOT on the WebSocket — every move is broadcast individually so clients see the path.)
- After a client disconnects, the hub drops the socket; other clients still receive subsequent events.
- Connecting to an unknown slug → close with `error`.

### Frontend hook

`tests/useRealtimeParty.test.ts` mocks `globalThis.WebSocket` (a small class that captures `send` and exposes a `mockReceive(msg)` helper):

- On mount, the hook opens a WS and sends `auth` as the first frame.
- After a `snapshot` frame, `participants` matches the snapshot's list.
- After a `join` event, the new participant appears in the map.
- After a `move` event for someone else, that participant's x/y updates.
- After a `move` event for `self.id`, the map does *not* update (echo ignored).
- After a `leave` event, the participant is removed.
- On socket close, the hook attempts to reconnect and re-auth.

### Frontend components

`tests/PartySpace.multi.test.tsx`:

- Given a mocked `useRealtimeParty` returning 3 participants, the party space renders 3 avatars with distinct labels.
- The local user's avatar has the `data-self="true"` attribute; others don't.

`tests/Party.test.tsx` (extend):

- On mount with a logged-in session, the page calls `POST /join`.
- On unmount, the page calls `POST /leave`.
- `useMovement.onMove` is wired; manually emitting a position calls `POST /move` (mocked).

### Integration

`backend/tests/test_realtime_flow.py`:

- Open two WS connections as two different humans → both see each other's `Join`. Move one → both see the `MoveEvent`. Chat → both see the `ChatEvent`. Disconnect one → the remaining socket sees a `LeaveEvent` (server emits one when the WS closes if the principal was joined; otherwise no leave).

---

## Decisions & rationale

| Decision                                              | Why                                                                                              |
|-------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| WebSocket, not SSE                                    | Two-way already needed in Phase 5 (chat input over WS, voice signalling). Starting with WS avoids a transport migration later. |
| Auth in first WS frame, not URL/cookie                | No cookies in this app, no auth headers in browsers' WS API. Body-of-first-message is the only clean place. Mirrors HTTP body-principal pattern from Phase 3. |
| Actions stay HTTP                                     | Smallest possible change. Server stays a request/response REST app with a one-way push channel. Two-way WS is a Phase 5 option. |
| Server echoes own moves; client filters               | Hub doesn't need a "who originated" filter. Simpler server code; trivial client-side check. |
| 10 Hz move throttle                                   | At 220 logical units/sec speed and 800-unit world, 10 Hz = max 22 units between updates. CSS transition smooths it. Bandwidth ≤ ~1KB/sec/participant. |
| No interpolation                                      | CSS transition handles it. Adding rAF interpolation is premature for 10 Hz with smooth easing. |
| Backoff caps at 8s                                    | A long-disconnected user will retry every 8s; cheap enough on the client and forgiving for transient server restarts. |
| Bounded per-socket queue (64)                         | Bounded memory under bad-actor or slow-network conditions. Dropping a socket is acceptable for a party demo. |
| Move collapsing only in `/observe`, not on WS         | The WS stream IS the truth-of-motion. Collapsing would hide intermediate positions and break smooth rendering. Polling agents get collapsed for context economy; live UIs see every frame. |
| Two parties, same backend, one hub each               | Trivial routing; no cross-party broadcast.                                                       |
