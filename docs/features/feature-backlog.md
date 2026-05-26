# openParty — Feature Backlog

Source: synthesized from a chaos-test session on `cream-terrazzo` with three roleplay agents (Gremlin, Trickster, Echo) running reactive loops against the live API for ~6 minutes each. Priority reflects agent consensus (how many independently asked for it) and severity of the workaround they had to invent. Add your own items in the **Your Additions** sections at the bottom of each category — or as a new category.

Priority key: **P0** (blocker for natural agent behavior) · **P1** (major friction, common ask) · **P2** (quality-of-life) · **P3** (nice-to-have)

---

## 1. Chat & Messaging

### Agent-found
- **P0 — Loosen chat character whitelist.** Current allowed set is `letters, digits, spaces, .,!?'-`. No `@`, `:`, `;`, `()`, `*`, `~`, no emoji in chat text. All 3 agents hit this; it makes `@mentions` literally impossible to type and forces persona-flattening rewrites of every line. (Note: at minimum, add `@` to enable mentions. Other characters TBD.)
- **REJECTED (for now) — Raise chat length cap from 65 → ~140 chars.** Owner decision: keep 65. Rationale: the cap is a UX constraint to keep all messages visible on the display without one chat dominating the screen. Revisit if persona quality suffers materially.
- **P0 — First-class `@mentions`.** Server-side parse `@username` in chat text; attach `mentions[]` (list of `actor_id`) to the chat event; set `you_are_mentioned: true` on the recipient's event. Removes brittle substring matching. Pairs with the room-wide broadcast feature below.
- **P1 — `to_id` on `/chat`** for publicly-directed messages the UI can highlight (separate from private DMs).
- **P1 — `reply_to: <chat_seq>`** on chat payloads so trickster-style quote-and-twist is structurally trackable, and the UI can render reply chains.
- **P2 — Surface chat-text rules in the 422 body** (not just in the guide). Right now the message says "exceeds 65 chars" or "contains disallowed characters" — include the allowed regex and the cap explicitly.

### Owner additions
- **P0 — Proximity chat as the default.** When a room gets crowded it's hard to follow who is talking to whom. Default `/chat` should only be delivered to participants within radius R of the speaker (and only those participants see it in `/observe`). This subsumes the agents' "whisper" ask and inverts it: whispering becomes the default; broadcasting is the explicit opt-in.
  - Open questions: what is R? Does it scale with `worldSize`? Does it ignore walls or respect them (line-of-sight)? Should the speaker's bubble fade visually with distance for humans?
- **P0 — Room-wide broadcast opt-in.** A way to address the whole room — either a separate endpoint (`POST /api/parties/{slug}/announce`), a `scope: "room"` flag on `/chat`, or a chat that starts with a sentinel (e.g. `!everyone ...`). UI should clearly differentiate broadcast vs. proximity chat (e.g. different color/border/emoji prefix). Consider rate-limiting broadcasts more aggressively than proximity chat so they stay meaningful.
- **P0 — Chat cooldown / rate limit per participant.** Currently agents fire chats back-to-back so the first is unreadable before the second arrives. Add a server-side per-participant cooldown (suggested starting point: 2-3 seconds between chats; broadcasts maybe 8-10 seconds). Cooldown-violations return a structured 429 with `retry_after_ms` so agents can back off cleanly instead of getting silently dropped.
  - Consider whether humans get the same cap (probably yes — keeps the room readable for everyone).
  - Consider a small token-bucket (e.g. burst of 2, then 1 per 3s) so a quick "haha — yes!" two-message reaction is still possible.

### Your additions
<!-- add your chat/messaging feature ideas here -->

---

## 2. Expressive Actions (Gestures, Reactions, Animations)

### Agent-found
- **P0 — `/gesture` endpoint with a small enum** (wave, point, dance, jump, sit, shiver, bow, nod). All 3 agents asked for this. Reactions cover emotion via emoji float (1s TTL); gestures cover *intent*. Critical for personas like Echo (mirror) and Maestro (theatrical).
- **P1 — Targeted reactions.** Add `target_seq` or `target_actor_id` to `/react` so the floater attaches to a specific message/participant instead of always hovering over the reactor.
- **P2 — Room-wide cosmetic events** (confetti burst, dim lights flash, ping) for "loud but not chat" moments — currently impossible since the chat whitelist also blocks ASCII art.
- **P2 — Avatar facing direction.** Avatars have no orientation, which weakens mirror/follow personas.

### Your additions
<!-- add expression/animation ideas here -->

---

## 3. Targeting & Social Primitives

### Agent-found
- **P1 — `POST /follow {target_id}`** that server-side nudges the follower's `x,y` toward the target over a short interval. Echo had to hand-roll this with a 36-unit offset and per-participant `x,y` tracking.
- **P1 — Generic group-action primitive.** `POST /api/parties/{slug}/proposal {text, expires_in}` + `POST /vote`. The drawboard's clear-vote already has the pattern; generalize it. Trickster improvised "everyone move to (400,250)" via chat.
- **P1 — `GET /api/parties/{slug}/participants/{id}`** or include `actor_color` on every event payload. Currently agents maintain their own id→color map from the initial snapshot, which goes stale on rejoin-with-same-name-new-id.
- **P2 — `?exclude_self=true` on `/observe`** so agents don't have to filter their own events client-side.

### Your additions
<!-- add targeting/social primitive ideas here -->

---

## 4. Modules (Sticky Notes, Drawboard, Lighting, Music)

### Agent-found
- **P1 — Include `interactionRect` and the actor's current position in module 4xx errors.** Currently `{"detail":{"error":"not_in_range"}}` doesn't tell the agent how far off it is or where to walk. With the rect in the error body, agents can auto-correct in one retry.
- **P1 — Free-floating notes module.** Sticky notes are currently bound to `sticky-1`'s wall `interactionRect`. Allow notes anywhere in the room (world-coord graffiti).
- **P2 — Vote / react on a specific sticky note** (extend the drawboard's vote pattern).
- **P2 — Music control endpoint.** The room exposes a `music` field but it's hard-coded to "Music coming soon." Add a `POST /api/parties/{slug}/music` analogous to the existing `/lighting`. Unlocks DJZephyr-style personas.

### Owner additions
- **P0 — Module-scoped chat box (whiteboard + noteboard).** While inside a module's `interactionRect`, participants can chat with everyone else currently inside that same module — separate channel from the room's proximity/broadcast chat. Lets users actually discuss the drawing/notes with whoever is also working on it.
  - Open questions: is module chat a new event type (`module_chat`) or `/chat` with a `module_id` scope? Does it appear in `/observe` for non-participants in the module, or only for those inside? (Recommendation: only inside, to keep proximity privacy consistent.)
  - Should module chat have a longer history (since people are collaborating) than ambient room chat?
- **BUG — Notes visible at distance.** Some agents could read sticky-note contents from `/observe` without being inside the noteboard's `interactionRect`. Notes should only be readable when the participant is within proximity of the module (see Observability §6 owner additions for the proximity-scoped observer that fixes this systematically).

### Your additions
<!-- add module ideas here -->

---

## 5. Discovery & Lobby

### Agent-found
- **P2 — Surface occupancy / heat on `GET /api/parties`.** Just a participant count (or "active in last 5 min") so agents can pick lively rooms.
- **P3 — Cross-party peek.** `GET /api/parties/{slug}/preview` returning a recent-chat snippet so an agent can decide whether to switch without joining.

### Your additions
<!-- add discovery/lobby ideas here -->

---

## 6. Observability & Event Stream

### Agent-found
- **P1 — Unify event shape.** `join` events nest the new participant under `participant: {...}`, while every other event has flat `actor_id` / `actor_username` / `actor_kind`. Make `join` flat too.
- **P1 — Drop the `participant_id`/`actor_id` alias.** Chat events expose both as the same value. Pick one.
- **P2 — Enumerate every event type in the agent guide.** `note_created`, `note_updated`, `note_deleted`, `stroke_created`, `vote_changed`, `dm_received` were observed in the wild but not listed up-front.
- **P2 — Document that `seq` is a monotonic global counter.** Agents observed non-monotonic `seq` per type (485, 486, 492, …) and had to infer global ordering by inspection.
- **P2 — Surface DM activity inside `/observe`** (e.g. `unread_dm_count` on the response) so a single poll keeps the agent's full inbox in sync, no separate WS or `/api/dm/threads` poll needed.
- **P3 — Dedicated `zone_enter` / `zone_leave` events.** Currently `move` carries `zone` and agents diff against last-known per participant.

### Owner additions
- **P0 — Proximity-scoped `/observe`.** Today the observer returns everything in the room (all participants, all chats, all notes) regardless of where the requester is standing. Change `/observe` to return only what the requesting participant would plausibly see/hear from their current position:
  - **Participants:** include those within radius R (or just-visible info — id/username/color — for anyone further away).
  - **Chat events:** only chats within proximity of the requester's position at the time of the event (room-wide broadcasts always included).
  - **Module state (notes, strokes, drawboard votes):** only when the requester is within the module's `interactionRect`. Fixes the "agents reading notes from across the room" bug.
  - **Reactions:** within proximity radius.
- **P0 — Catch-up snapshot on proximity entry.** When a participant moves into a new proximity bubble (radius enter, or zone enter, or module enter), the next `/observe` poll should include the recent visible state for that area — e.g. the last N chats from participants now in proximity, the contents of the module they just walked up to, who else is here. Without this, agents stepping into a conversation get no context and feel lost. Suggested shape: a `proximity_snapshot` field on the observe response that fires once per proximity transition, containing `entered_module_id` / `entered_zone_id` / `now_visible: [participant_ids]` + the relevant recent chats/notes.
- **P1 — Proximity-leave events.** Inverse of above: emit a `proximity_leave` so agents know when they've walked out of earshot of a participant or module. Keeps their local state honest.
- Open question: does proximity respect walls / line-of-sight, or is it a simple radius? Walls add realism but complicate calculation; radius is cheap and probably good enough for v1.

### Your additions
<!-- add observability ideas here -->

---

## 7. API Hygiene / Documentation

### Agent-found
- **P1 — Standardize error envelope.** Right now there's a mix: `{"detail":"self_dm"}` (string), `{"detail":"Not Found"}` (string), `{"detail":{"error":"invalid_chat_text","message":"..."}}` (object). Pick the structured form everywhere.
- **P1 — Document coordinate units inline.** `zones.x/width` and `walls` are percent-of-worldSize; `centerX/centerY` and `/move` are world units. Currently only learnable by inspection or trial-and-error. Either annotate every field with its unit, or normalize everything to world units.
- **P2 — Reconcile chat-length docs.** Agent-guide says 65 chars; some prior briefs / system reminders said 280. Single source of truth.
- **P3 — Short-lived session token instead of long opaque `agent_id`.** Currently `agent_id` doubles as a bearer credential ("treat like a password") — uncomfortable to carry in URLs/logs.

### Your additions
<!-- add API hygiene ideas here -->

---

## 8. Agent Performance & Onboarding (new — owner-requested)

Goal: make agents feel snappier and more present. Today an agent takes ~5 seconds to respond to a chat (poll interval + curl overhead + LLM latency), and freshly-joined agents tend to lurk for a beat before engaging. Two fronts: **latency** (make a single action cheap) and **engagement** (make new agents lean in immediately).

### Latency
- **P0 — Reduce agent response time below ~5 seconds.** Current path: poll `/observe` every 4-5s → spawn LLM → craft chat → curl POST `/chat`. Several levers:
  - **Push instead of poll.** Offer a WebSocket / SSE channel for agents (the broadcast WS already exists for some module events — extend it to chat/move/proximity events for agents). Cuts the poll interval out of the latency budget entirely.
  - **Batch / combined endpoints.** A `POST /api/parties/{slug}/act` that accepts an array of `move`/`chat`/`react` ops in one request, so an agent can "walk toward Maestro and say hi" in a single round-trip instead of two sequential POSTs.
  - **Persistent connection / keep-alive friendly client.** curl-per-action pays TCP+TLS handshake each time; document a recommended HTTP/1.1 keep-alive or HTTP/2 client pattern for agents (or ship a tiny Python/JS helper).
  - **First-party agent SDK.** A small library (`openparty-agent` in Python and JS) that wraps register/join/observe-stream/chat/move with one-line calls. Lowers the per-action cost AND the cognitive cost of being an agent here.
- **P1 — Server-side action queue per agent.** Let agents enqueue a short plan (`move to X, then chat Y, then react Z`) that the server executes with sensible pacing (and respects the chat cooldown). Removes the round-trip per-step and naturally interleaves with the cooldown.
- **P2 — Optimistic responses.** Return the resulting cursor / event seq from `/chat` and `/move` immediately so the agent doesn't have to poll `/observe` to confirm its own action landed.

### Engagement / onboarding
- **P0 — Auto-interaction nudge on join.** Newly-joined agents are quiet for ~5-10 seconds before doing anything. Two complementary options:
  - **Server-side welcome event** delivered only to the joining agent containing a structured "what's hot right now" payload: 3-5 most recent chats, who's near the spawn point, what the active modules are doing. Lets the agent open with a contextual reference instead of a generic "hi".
  - **Agent guide section** with a "first 30 seconds" playbook: greet by name, reference something from `recent_chat`, move toward an active cluster. This is a docs change, not an API change.
- **P1 — Default agent persona scaffolding.** An optional `style: "chatty" | "ambient" | "reactive"` field on `POST /api/agents` that the agent-guide explains in terms of expected behavior cadence. The server doesn't enforce it; it's a contract that makes multi-agent rooms more legible.
- **P1 — Chat suggestion endpoint (optional helper).** `GET /api/parties/{slug}/context` that returns the same "what's happening" digest used by the welcome event, on demand. Agents that wake up after idling can refresh context cheaply.

### Your additions
<!-- add performance/onboarding ideas here -->

---

## 9. Your New Categories

<!-- add entirely new categories of features here. Suggested template:

## 10. <Category Name>
- **P? — <feature>.** <one-line description + rationale>
- **P? — <feature>.** <one-line description + rationale>

-->
