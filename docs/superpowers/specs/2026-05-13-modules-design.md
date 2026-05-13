# Modules: Reactions, Lighting, Sticky Notes, Drawing Board

**Date:** 2026-05-13
**Status:** Design (approved by user 2026-05-13)
**Depends on:** Phase 4 multiplayer realtime (`2026-05-12-phase4-multiplayer-design.md`)

## Goal

Add cozy, ambient, agent-friendly ways to interact in a party beyond chat. Every feature is a **module**: a plug-and-play unit a party config opts into. Humans and agents interact with modules under the same rules — agents must walk over to use them, just like people.

The first slice of modules:

- **Reactions** (always-on) — emoji floats above an avatar.
- **Lighting** (room-level) — preset tints the whole room.
- **Sticky notes** (placed) — per-user notes on a shared wall.
- **Drawing board** (placed) — collaborative shared sketch surface.

## Non-goals (out of scope for this spec)

- Persistence across backend restarts (notes/strokes vanish on restart, same as today's world state).
- Host/role permissions (anyone in the party can change lighting; anyone in a board's zone can vote to clear).
- Eraser / per-stroke undo on the drawing board.
- Freeform emoji input for reactions (fixed allow-list only).
- Per-module configurable options (e.g. `maxNotesPerUser`). Defaults are hard-coded in v1.
- Avatar-vs-avatar collision. Stacking is mitigated by approach-slot jitter, not by collision detection.

---

## 1. Module system

### Module shape

`PartyConfig` gains a `modules: Module[]` field:

```ts
type PlacedModule =
  | { id: string, kind: "stickynotes", x: number, y: number, w: number, h: number }
  | { id: string, kind: "drawboard",   x: number, y: number, w: number, h: number };

type RoomModule =
  | { id: string, kind: "lighting", preset: "day" | "dusk" | "night" | "party" };

type Module = PlacedModule | RoomModule;
```

- **Placed modules** (`stickynotes`, `drawboard`) live in the room at world coordinates with a footprint.
- **Room modules** (`lighting`) have no footprint; they affect the whole room.
- Reactions are **not** a module — they are an always-on capability of every avatar.

### Module IDs

Stable, derived from the config:
- Placed modules: `{kind}-{1-based-index-among-same-kind}` — e.g. `sticky-1`, `draw-1`.
- `lighting` is room-level and at most one per party, so its id is the bare string `lighting`.

IDs are stable across restarts so agents can address them by name.

### Interaction zone

Each placed module exposes `interactionRect = footprint inflated by INTERACTION_MARGIN (24px)`. An actor must be inside this rect to perform any action on the module. The server validates on every action — out of range returns `409 not-in-range`.

### Approach slots (anti-stacking)

Each placed module declares **6 approach slots** evenly spaced along the side of the interaction rect that faces the room interior. Each slot is an `(x, y)` point inside the interaction zone.

A slot is **occupied** if any participant's current position is within `SLOT_OCCUPIED_RADIUS (32px)` of the slot.

Slots are surfaced in `/observe` (see Section 6) so agents can pick a free slot and move to it via the normal `/move` endpoint. There is no separate "approach" endpoint.

### Frontend rendering

A generic `<Module>` component dispatches by `kind` to `<StickyWall>`, `<DrawBoard>`, etc. Each subscribes to its slice of the realtime event stream. Modules are rendered in the room's world coordinate space, like zones.

---

## 2. Reactions (always-on)

### Shape

```ts
type Reaction = { actor_id: string, emoji: string, expires_at: ISOString };
```

- Floats above the actor's avatar for **1 second**, then disappears.
- An actor can have at most one active reaction at a time. A new reaction replaces the old.
- The 1-second lifetime is the cooldown (no separate cooldown logic).

### Emoji allow-list

Fixed, 12 entries:

```
❤️ 😂 👀 🎉 👍 👋 🤔 😮 🔥 ✨ 😴 🫶
```

Defined in `backend/app/validation.py` as `REACTION_EMOJI_ALLOWLIST`. Unknown emoji → `400`.

### API

```
POST /api/parties/{slug}/react
  body: { principal: {kind, id}, emoji }
  errors: 400 unknown_emoji, 404 slug, 409 not_joined
```

### Frontend

A small emoji palette in the room overlay (12 buttons). Clicking pops the reaction. Reactions appear over avatars via a positioned overlay.

---

## 3. Lighting (room-level)

### Shape

Lives in `PartyConfig.modules` as initial state and in `PartyWorld` runtime state so it can change without editing the config file.

```ts
type LightingPreset = "day" | "dusk" | "night" | "party";
```

Each preset maps to a tint color + opacity in the frontend (e.g. `night = rgba(20, 30, 80, 0.35)`, `party = rgba(255, 80, 200, 0.18)`). Day is a no-op / very faint warm tint.

### Permissions

**Anyone in the party can change lighting.** No host role yet. Easy to gate later.

### API

```
POST /api/parties/{slug}/lighting
  body: { principal, preset }
  errors: 400 unknown_preset, 404 slug, 409 not_joined
```

### Frontend

A single `<div>` overlay sits above the room with `pointer-events: none` and `mix-blend-mode: multiply` (or similar). Its background color comes from the active preset. Changing preset interpolates with a short CSS transition (~300ms) so the room doesn't jump.

---

## 4. Sticky notes (placed module, per-user ownership)

### Note shape

```ts
type StickyNote = {
  id: string,
  module_id: string,        // which wall it lives on
  author_id: string,        // session_id or agent_id
  author_kind: "human" | "agent",
  text: string,              // <= STICKY_TEXT_MAX (140 chars), passes existing chat regex
  color: "yellow" | "pink" | "blue" | "green",
  x: number,                // local to wall rect, [0, w]
  y: number,                // local to wall rect, [0, h]
  created_at: ISOString,
};
```

### Rules

- Only the author can `PATCH` or `DELETE` their own note (mismatch → `403`).
- Max **10 notes per user per wall** (additional `POST` → `409 limit_reached`).
- `text` validated against the existing `CHAT_TEXT_REGEX`; max length **140**.
- `x, y` clamped to the wall rect on the server.
- All actions require the actor to be in the wall's interaction zone (`409 not-in-range`).

### API

```
POST   /api/parties/{slug}/modules/{module_id}/notes
       body: { principal, text, color, x, y }
PATCH  /api/parties/{slug}/modules/{module_id}/notes/{note_id}
       body: { principal, text?, color?, x?, y? }
DELETE /api/parties/{slug}/modules/{module_id}/notes/{note_id}
       body: { principal }
```

### Frontend

Notes render in-place on the wall (visible from anywhere in the room). When the user's avatar is inside the interaction zone, an "+ add note" affordance appears; the user clicks where on the wall to drop the note, then types in an inline editor. Drag-to-move and click-to-edit are available only for the user's own notes and only while in the zone.

---

## 5. Drawing board (placed module, collaborative)

### Stroke shape

```ts
type Stroke = {
  id: string,
  module_id: string,
  author_id: string,
  author_kind: "human" | "agent",
  color: AvatarColor,             // reuse existing color allow-list
  width: "thin" | "med" | "thick",
  points: { x: number, y: number }[],   // local to board rect
  created_at: ISOString,
};
```

Strokes are **append-only**. Render order = creation order.

### Limits

- Max **500 strokes per board** total — when exceeded, the oldest stroke is dropped (FIFO) and a `stroke_dropped` event is emitted so clients can drop it from local state.
- Max **200 points per stroke**. The client subdivides long strokes; the server rejects oversized strokes with `400`.
- Points outside the board rect are clamped to the rect on the server.

### Tools (v1)

- Color: avatar color allow-list (the existing 12 fixed swatches).
- Width: `thin | med | thick` (e.g. 2 / 5 / 10 px).
- No eraser, no per-stroke undo in v1.

### Vote-to-clear

`POST .../clear` is a **vote**, not an immediate clear.

- Server stores `{ module_id → { actor_id → vote_expires_at } }`.
- A vote auto-expires after **30 seconds**.
- A vote counts only while the voter is currently in the interaction zone. The server recomputes the tally:
  - On every new vote.
  - When any participant moves (zone entry/exit may change population and which votes count).
  - When any active vote expires.
- The board clears when `active_votes > zone_population / 2` (strict majority). Solo voter clears immediately (1 > 0.5). Two voters need both. Three need two.
- Agents in the zone vote and are counted in the population, same as humans.
- On clear: all strokes are dropped, all votes are cleared, and a `board_cleared` event is emitted.

### API

```
POST /api/parties/{slug}/modules/{module_id}/strokes
     body: { principal, color, width, points }
     errors: 400 invalid_stroke, 404 slug, 409 not_joined | not_in_range
POST /api/parties/{slug}/modules/{module_id}/clear
     body: { principal }
     errors: 404, 409 not_joined | not_in_range
     response: { votes, needed, cleared: boolean }
```

### Frontend

While the user's avatar is inside the interaction zone, the board's `<canvas>` (or SVG layer) captures pointer events. Drag = draw; pointer-up = commit one POST per completed stroke. Incoming strokes render in real time. A vote-to-clear button shows `Clear (n/m)` and is enabled while in the zone.

---

## 6. Realtime events + `/observe`

### New event types

Added to the existing event log. All ride the Phase 4 WebSocket channel and appear in `/observe` cursor diffs.

| Type | Payload |
|---|---|
| `reaction` | `{ actor_id, emoji, expires_at }` |
| `lighting_changed` | `{ preset, changed_by }` |
| `note_created` | `{ module_id, note }` |
| `note_updated` | `{ module_id, note }` |
| `note_deleted` | `{ module_id, note_id }` |
| `stroke_added` | `{ module_id, stroke }` |
| `stroke_dropped` | `{ module_id, stroke_id }` (FIFO eviction) |
| `board_cleared` | `{ module_id, cleared_by: actor_id }` |
| `vote_changed` | `{ module_id, votes, needed }` |

Consecutive `vote_changed` events for the same board collapse to the latest in `/observe` diffs (same pattern as `move`).

### `/observe` snapshot additions

```jsonc
{
  // ... existing fields (room, participants, cursor) ...
  "modules": [
    {
      "id": "sticky-1",
      "kind": "stickynotes",
      "x": 100, "y": 100, "w": 300, "h": 200,
      "interactionRect": { "x": 76, "y": 76, "w": 348, "h": 248 },
      "approachSlots": [
        { "x": 130, "y": 320, "occupied": false },
        // ... 5 more ...
      ],
      "notes": [ /* StickyNote[] */ ]
    },
    {
      "id": "draw-1",
      "kind": "drawboard",
      "x": 500, "y": 100, "w": 300, "h": 200,
      "interactionRect": { /* ... */ },
      "approachSlots": [ /* ... */ ],
      "strokes": [ /* Stroke[] */ ],
      "vote": { "votes": 0, "needed": 1 }
    }
  ],
  "lighting": { "preset": "dusk" },
  "active_reactions": [ /* Reaction[] */ ]
}
```

---

## 7. Agent guide additions

`/api/agent-guide` markdown gains a "Modules" section covering:

- How to discover modules: read `modules`, `lighting`, `active_reactions` from `/observe`.
- How to approach a module without stacking: pick a slot from `approachSlots` where `occupied == false`, move to its `(x, y)` via `/move`.
- The "must be in interaction zone" rule for all module actions.
- Reaction emoji allow-list and the 1-second lifetime.
- Voting semantics for `drawboard.clear`.
- A worked example: "approach the drawing board and draw a smiley."

---

## 8. Module enablement per party

A party author controls which modules exist by listing them in `PartyConfig.modules`. To omit a module, leave it out. To enable several, place them with non-overlapping footprints (server warns on overlap at startup; not a hard error).

Example for the Cream Terrazzo Lounge:

```ts
modules: [
  { id: "lighting", kind: "lighting", preset: "dusk" },
  { id: "sticky-1", kind: "stickynotes", x: 80,  y: 60,  w: 240, h: 160 },
  { id: "draw-1",   kind: "drawboard",   x: 480, y: 60,  w: 320, h: 200 },
]
```

---

## 9. File-layout impact

**Backend** (`backend/app/`):
- `models.py` — add `Module`, `StickyNote`, `Stroke`, `Reaction`, lighting preset enum.
- `validation.py` — add `REACTION_EMOJI_ALLOWLIST`, `STICKY_TEXT_MAX`, `STROKE_MAX_POINTS`, `STROKES_PER_BOARD_MAX`, `NOTES_PER_USER_MAX`, `INTERACTION_MARGIN`, etc.
- `world.py` — `PartyWorld` gains per-module state (notes, strokes, votes, lighting, active reactions) and helper methods (`in_zone`, `tally_votes`, `evict_oldest_stroke`).
- `events.py` — new event models.
- `routes/` — new files: `reactions.py`, `lighting.py`, `module_notes.py`, `module_drawboard.py`. Keep routes ~under 300 lines per CONVENTIONS.

**Frontend** (`frontend/src/`):
- `parties/` — extend `PartyConfig` types with `modules`.
- `components/modules/` — new directory: `Module.tsx` (dispatcher), `StickyWall.tsx`, `DrawBoard.tsx`, `LightingOverlay.tsx`, `ReactionLayer.tsx`, `ReactionPalette.tsx`.
- `hooks/` — `useModuleEvents.ts` (subscribe per-module slice of the WS stream), `useInteractionZone.ts` (is my avatar in zone X?).
- `api/` — extend the fetch client with module endpoints.

Existing `useMovement` and wall-collision logic are not touched. Approach slots are points, not walls.

---

## 10. Testing strategy

Following TDD per CONVENTIONS:

**Backend (pytest):**
- Interaction-zone gating: every module endpoint rejects out-of-zone with `409`.
- Sticky note ownership: PATCH/DELETE from non-author → `403`.
- Sticky note limit: 11th note from same user → `409`.
- Reaction allow-list: unknown emoji → `400`.
- Reaction replacement: second reaction from same actor replaces the first.
- Lighting: anyone in party can change; unknown preset → `400`.
- Stroke point clamping and oversized-stroke rejection.
- FIFO eviction at the 501st stroke; `stroke_dropped` emitted.
- Vote-to-clear math: solo voter clears immediately; 1-of-2 doesn't; 2-of-3 does.
- Vote drops when voter leaves the zone (move triggers recompute).
- Vote expires after 30s.
- `/observe` snapshot includes modules + slot occupancy.

**Frontend (vitest + RTL):**
- `ReactionPalette` posts emoji and clears after 1s.
- `LightingOverlay` reflects preset changes from the event stream.
- `StickyWall` renders notes, restricts editing to author, hides "+ add" when out of zone.
- `DrawBoard` captures pointer only while in zone; commits one POST per stroke.
- Vote indicator updates from `vote_changed` events.

**Cross-stack contract test:** existing test that verifies TS party slugs match the API extended to also check module IDs match between TS config and `/parties/{slug}` response.

---

## 11. Open questions deferred to implementation

- **Snapshot size:** if `strokes` and `notes` in `/observe` get large, switch to a stroke-count + lazy-fetch endpoint. Decide during implementation based on real payload sizes.
- **Module overlap at config time:** warn on overlap; consider a stricter validator later.
- **Lighting transition timing:** 300ms feels right; tune in implementation.
