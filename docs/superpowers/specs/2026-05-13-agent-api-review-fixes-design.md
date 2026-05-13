# Agent API Review Fixes — Design

**Date:** 2026-05-13
**Branch:** `fix/agent-api-review`
**Scope:** Address 8 reviewer findings on the agent-facing API. One bug-fix branch, one PR. Guiding principles: **consolidation and simplicity**.

## Background

The Phase 3 agent API shipped with eight reviewer findings of varying severity. The largest is a fairness bug — humans are blocked by walls, agents are not — caused by collision living only in the frontend. The rest are small contract issues (unit mismatch, missing fields, weak error codes) and documentation gaps (color palette, poll cadence, bearer-token warning).

WebSocket / SSE work is explicitly **out of scope** for this round; Phase 4 design lives in `docs/superpowers/specs/2026-05-12-phase4-multiplayer-design.md`.

## Goals

- Eliminate the human/agent wall-collision asymmetry by enforcing collision in the world model.
- Make the agent contract self-describing: an agent reading `/api/agent-guide` plus `/api/parties/{slug}` plus `/observe` should never need to read TypeScript source to participate correctly.
- Stable, machine-readable error codes so agents can self-heal across backend restarts.
- No new endpoints. No schema breaks.

## Non-Goals

- Long-poll, SSE, or any push transport (Phase 4).
- Persistence / restart survival (Phase 4+).
- Rate limiting, real auth, avatar-vs-avatar collision.

## Per-Issue Fix

### 1. Server-side wall collision (slide semantics)

**Problem.** `useMovement.ts` enforces wall collision; `world.move()` only clamps to world bounds. Agents using `/move` walk through furniture.

**Fix.** Port the inflated-rect + X/Y slide algorithm into the world model.

- New module `backend/app/collision.py`:
  - `AVATAR_RADIUS = 14` (Python source of truth; mirror with a comment in `frontend/src/hooks/useMovement.ts`).
  - `inflate_walls(walls, world_size) -> list[Rect]` — converts percent walls to absolute rects, inflated by `AVATAR_RADIUS`.
  - `slide(from_pt, to_pt, rects, world_size) -> Point` — if the target point is inside any rect, try (to.x, from.y); if that is also blocked, try (from.x, to.y); if both blocked, return `from`. Then clamp to world bounds.
- `PartyWorld.__init__` precomputes inflated rects once.
- `PartyWorld.move(participant_id, x, y)` calls `slide(current, requested, rects, world_size)` and stores the result.
- **No new error code** for in-wall moves. They slide or no-op. The route still returns 200 with the resulting `{x, y, zone, cursor}`. This matches the human UX exactly: walking into a wall does not error, you just stop.

The frontend keeps its prediction logic for smooth WASD. The two implementations must agree on `AVATAR_RADIUS` — duplicate with a cross-pointer comment.

### 2. Zone centers in world units

**Problem.** Zones in `/api/parties` use percent of `worldSize`; `/move` takes absolute world units. Agents must do the conversion themselves.

**Fix.** Add **derived** `centerX` / `centerY` (world units, floats) to each zone in the `_room_view` payload returned by `GET /api/parties/{slug}` and `GET /observe` (initial snapshot only). Computed as:

```
centerX = (zone.x + zone.width / 2)  * worldSize.width  / 100
centerY = (zone.y + zone.height / 2) * worldSize.height / 100
```

Existing `x/y/width/height` percent fields stay — frontend renderer uses them and we do not break it.

Update `/api/agent-guide` with one line: "To move to a zone, post `{x: zone.centerX, y: zone.centerY}`."

### 3. Discoverable color palette

**Problem.** Agent guide lists 3 example colors; 422 on bad color says nothing about the allowed set.

**Fix.**

- Agent guide embeds the full literal list from `ALLOWED_COLORS`.
- `POST /api/agents` 422 detail becomes `{"error": "invalid_color", "allowed_colors": [...]}`.
- No new endpoint.

### 4. Polling guidance

**Problem.** No backpressure hint; eager agents may hammer `/observe`.

**Fix.** One paragraph in `/api/agent-guide`:

> Poll `/observe` every 1–2 seconds. Consecutive `move` events from the same participant are collapsed into one entry with the latest position, so polling cadence does not affect correctness — only freshness.

No server change. Real backpressure waits for Phase 4 SSE.

### 5. Event ordering in `/observe` diffs

**Problem.** `observe_since` emits non-move events in encounter order, then move entries from a dict. A `chat` with `seq:7` can land before a `move` with `seq:6`.

**Fix.** Sort `out` ascending by `seq` at the end of `observe_since`. One line.

### 6. `at` timestamp on all event types

**Problem.** Only `ChatEvent` has `at`. `MoveEvent`, `JoinEvent`, `LeaveEvent` don't.

**Fix.** Add `at: float` to `JoinEvent`, `LeaveEvent`, `MoveEvent`. Populate at construction in `PartyWorld`. Include in `observe_since` output dicts.

### 7. `agent_id` is a bearer token

**Problem.** Holding the id grants action. Guide doesn't say so.

**Fix.** One sentence under "Register" in `/api/agent-guide`:

> Treat `agent_id` like a password. Anyone who has it can act as your agent. Do not embed it in shared code or logs.

### 8. Distinct `principal_unknown` vs `not_in_party`

**Problem.** `resolve_principal` returns 401 `"invalid principal"` for unknown ids; party actions return 409 `"principal not in party"` when joined-state is missing. An agent that hits 409 after a backend restart cannot tell whether to re-register or re-join.

**Fix.** Stable, machine-readable detail strings:

- 401 from `resolve_principal` → `detail = "principal_unknown"`.
- 409 from party_actions on `ParticipantNotInPartyError` → `detail = "not_in_party"`.

Document both in `/api/agent-guide` under a new "Recovering from errors" section: on `principal_unknown` re-register; on `not_in_party` re-join.

We are **not** wrapping detail into an object (would be a contract break). The string itself becomes the code.

## File-Level Changes

| File | Change |
|---|---|
| `backend/app/collision.py` | **New.** `AVATAR_RADIUS`, `inflate_walls`, `slide`. ~60 LOC. |
| `backend/app/world.py` | Precompute inflated rects in `__init__`. `move()` calls `slide()`. `observe_since()` sorts by seq. Populate `at` on join/leave/move. |
| `backend/app/events.py` | Add `at: float` to `JoinEvent`, `LeaveEvent`, `MoveEvent`. |
| `backend/app/routes/party_actions.py` | `_room_view` zones include `centerX`/`centerY`. 409 detail → `"not_in_party"`. |
| `backend/app/routes/principal.py` | 401 detail → `"principal_unknown"`. |
| `backend/app/routes/agents.py` | 422 on color → detail includes `allowed_colors`. |
| `backend/app/routes/agent_guide.py` | Rewrite: full color palette, zone centers, poll cadence (1–2s), bearer-token warning, "Recovering from errors" section. |
| `frontend/src/hooks/useMovement.ts` | Add comment near `AVATAR_RADIUS` pointing at `backend/app/collision.py`. No behavior change. |

## Testing (test-first)

New pytest files under `backend/tests/`:

1. `test_world_collision.py`
   - Move directly into a wall → position unchanged (no-op).
   - Move diagonally into a wall edge → slides along the non-blocked axis.
   - Move into a corner where both axes are blocked → no-op.
   - Wall collision applies to both human and agent principals.
2. `test_observe_ordering.py` — interleaved chat/move/join produce ascending-by-seq output.
3. `test_event_at_timestamps.py` — every event type's `at` populated and within tolerance of `time.time()`.
4. `test_principal_unknown_code.py`
   - Delete a session, then call `/move` → 401 with `detail == "principal_unknown"`.
   - Join then leave then call `/move` → 409 with `detail == "not_in_party"`.
5. `test_zone_centers.py` — `centerX`/`centerY` present and correct on both `GET /api/parties/{slug}` and `GET /observe`.
6. `test_agents_color_error_detail.py` — 422 on bad color contains the allowed list.
7. `test_agent_guide_content.py` — guide mentions: every allowed color hex, `centerX`/`centerY`, "1–2", "password" or "bearer", `principal_unknown`, `not_in_party`.

Existing tests stay green; the contract additions are non-breaking.

## Out of Scope (Explicit)

- WebSocket / SSE push transport.
- Long-poll on `/observe`.
- Persistence across restarts.
- Avatar-vs-avatar collision.
- Rate limiting.
- Token-based auth (replacing `agent_id` as bearer).
