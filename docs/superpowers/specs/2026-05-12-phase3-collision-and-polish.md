# Phase 3 — openParty rename, visual polish, wall collision

**Date:** 2026-05-12
**Builds on:** Phase 1 + Phase 2 specs.
**Scope:** Cosmetic rename, two visual polishes, and a minimal wall-collision system that also makes click-to-move navigate around walls.

---

## 1. Rename to "openParty"

User-facing strings only — the repository, package names, and folder paths stay as `ai_agent_party`.

- `frontend/index.html`: `<title>openParty</title>`
- `frontend/src/pages/SignIn.tsx`: `<h1>Welcome to openParty</h1>`, plus a tagline `<p>` underneath: "Throw parties with humans and AI agents."

No other strings change. README and `CLAUDE.md` are out of scope.

---

## 2. SignIn polish

The form gains a card-style container and a more polished color picker. Specifically:

- The `<main>` becomes a card with `background: #fff`, `border: 1px solid #f0e6d8`, `border-radius: 16px`, `box-shadow: 0 10px 30px rgba(0,0,0,0.08)`.
- Outer container adds vertical centering on tall viewports.
- Title hierarchy: `<h1>` (clamp 24-36) is "Welcome to openParty"; below it a `<p class="subtitle">` (clamp 14-16, color `#666`).
- Color swatches: when selected, swatch shows a centered white `✓` and a subtle scale `transform: scale(1.1)` with `transition: transform 120ms ease`. Selected swatch outline stays.
- Submit button: pill-shaped, full-width on mobile (`width: 100%`), accent color from the cream-terrazzo palette `#ff6b9d`, white text, `box-shadow: 0 4px 10px rgba(255,107,157,0.30)`, hover `transform: translateY(-1px)`.

No behavior or test changes — existing SignIn tests must continue to pass. The "Enter" button label and `getByRole('button', {name: /enter/i})` selector stay valid.

---

## 3. Leave-party button polish

In `frontend/src/pages/Party.tsx`, the "Leave party" button becomes pill-shaped with:
- `background: ${party.theme.accent}` (uses the current party's accent — Cream Terrazzo is `#ff6b9d`)
- `color: white`, `border: none`, `padding: 8px 16px`, `border-radius: 999px`
- Icon prefix: `← Leave party`
- Hover: `transform: translateY(-1px)`, `box-shadow: 0 4px 10px rgba(0,0,0,0.15)`

Existing Party test asserts the redirect via clicking "Leave party" — wait, current test does not click it. No test changes needed.

---

## 4. Wall collision

### Schema
No schema change. `Wall` already exists.

### Algorithm

`useMovement` gains an optional `walls: Wall[]` field on its options. When omitted, behavior is the previous (no collision).

```typescript
const AVATAR_RADIUS = 14; // logical units, matches visible 28px circle

function wallRect(w: Wall, worldWidth: number, worldHeight: number) {
  const left = (w.x / 100) * worldWidth - AVATAR_RADIUS;
  const top = (w.y / 100) * worldHeight - AVATAR_RADIUS;
  const right = ((w.x + w.width) / 100) * worldWidth + AVATAR_RADIUS;
  const bottom = ((w.y + w.height) / 100) * worldHeight + AVATAR_RADIUS;
  return { left, top, right, bottom };
}

function isBlocked(point, rects) {
  for (const r of rects) {
    if (point.x > r.left && point.x < r.right &&
        point.y > r.top && point.y < r.bottom) return true;
  }
  return false;
}
```

Each frame, given the attempted `(x + dx, y + dy)`:
1. If not blocked → take it.
2. Else, if `(x + dx, y)` not blocked → take it (X-axis slide).
3. Else, if `(x, y + dy)` not blocked → take it (Y-axis slide).
4. Else, don't move.

This rule applies to both WASD motion and click-to-move lerping. Combined with the existing lerp logic, this produces "minimal pathfinding": the avatar slides along a wall until it clears the corner, at which point the lerp toward the click target resumes diagonally.

### Avatar starting position

If the initial `(worldWidth/2, worldHeight/2)` lands inside a wall (unlikely for Cream Terrazzo's geometry but possible for future parties), `useMovement` keeps the avatar there — collision only blocks *motion*, not initial placement. Authors should choose initial positions outside walls; we don't add a search step.

### Tests
- New: `useMovement does not enter a wall when WASD pushes into it` — set up a wall covering the right half of the world, hold "d", verify avatar's x never exceeds the wall's inflated left edge.
- New: `useMovement slides along a wall when clicking past it` — wall blocks direct path to target; verify avatar reaches a point near the target after enough ticks (sliding works).
- Existing useMovement tests stay green (they pass `walls: undefined` or `[]`).

---

## 5. Wiring

`PartySpace` passes `walls={party.room.walls}` to `useMovement`. Click-to-move still works the same way; the collision algorithm just filters motion.

---

## Out of scope

- Polygonal walls or non-axis-aligned walls (rectangles only).
- A* / waypoint pathfinding for complex maze geometry.
- Collision between avatars (no multiplayer yet).
- Collision with the room border itself — the avatar can still slide along the floor border via the existing world-bounds clamp.
- Search-from-spawn algorithm if initial position is inside a wall.

---

## Decisions

| Decision | Why |
|---|---|
| Avatar treated as a point + walls inflated by radius | Cheapest correct geometry. Equivalent to circle-vs-rect overlap test for axis-aligned rectangles. |
| Slide-along-axis algorithm | Minimal, deterministic, handles 95% of click-past-a-wall cases on simple wall stubs without any path planning. |
| No path planning | User asked explicitly for minimal. A* etc. would be premature for the geometry we have. |
| Walls optional on `useMovement` | Backward compatible with existing tests; keeps the hook reusable. |
