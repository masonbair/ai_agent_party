# Phase 2 — Room Shape, Boxy Zones, Responsive Layout, Lobby Previews

**Date:** 2026-05-12
**Builds on:** `2026-05-12-signin-and-party-page-design.md`
**Scope:** Visual + responsiveness polish based on user feedback. No new pages or backend behavior.

---

## Motivation

After Phase 1 shipped, the user reviewed and asked for four changes:

1. Lobby cards have a blank preview area — should show a mini party-room rendering.
2. Pages should scale per device (phone / tablet / laptop).
3. Party floor should feel like a room, with angles/walls and prominent boxy zones (not see-through ovals).
4. Future parties should be able to use different room shapes — extensibility is required.

---

## Schema Changes

### New `Wall` and `Room` types

```typescript
type Wall = {
  x: number;            // top-left, % of world width (0-100)
  y: number;            // top-left, % of world height (0-100)
  width: number;        // % of world width
  height: number;       // % of world height
  color: string;        // CSS color
};

type Room = {
  // Optional CSS clip-path. `null`/undefined renders a plain rectangle.
  // Example for L-shape: 'polygon(0 0, 70% 0, 70% 50%, 100% 50%, 100% 100%, 0 100%)'
  clipPath?: string | null;
  // Outer wall styling, e.g. "6px solid #8b6f47"
  border: string;
  // Optional border radius in px (defaults to 0)
  borderRadius?: number;
  // Interior wall stubs that visually separate zones without blocking movement.
  walls: Wall[];
};
```

### `Zone` gets an explicit `borderColor`

The existing `Zone.labelColor` already implied border emphasis; make it explicit:

```typescript
type Zone = {
  // ...existing fields...
  borderColor: string;  // NEW — required; defaults to labelColor in the seed data
};
```

Zone is now rendered as a **solid filled rectangle** with a **3px solid border** in `borderColor`. No more `radial-gradient` ellipse. Label sits in the top-left corner of the zone box, in white text on the colored fill (the existing `labelColor` becomes the border color in seed data; new prominent labels use white on the zone fill).

### `PartyConfig` gains `room: Room`

```typescript
type PartyConfig = {
  // ...existing fields...
  room: Room;
};
```

Backend pydantic model mirrors all of the above with the same field names.

### Cream Terrazzo seed values

- `room.clipPath`: null (rectangle for now)
- `room.border`: `"6px solid #8b6f47"`
- `room.borderRadius`: `12`
- `room.walls`: two stubs —
  - Vertical stub between dance & chill at the top: `{x: 50, y: 0, width: 0.75, height: 30, color: "#8b6f47"}` (0.75% of 800 ≈ 6px)
  - Horizontal stub on the right above snacks: `{x: 75, y: 40, width: 25, height: 0.75, color: "#8b6f47"}`
- Zone `borderColor` values match existing `labelColor` (dance `#8b1a4a`, chill `#00606e`, snacks `#6b3a00`)
- Existing zone `x/y/width/height` stay the same so movement logic is untouched.

---

## Rendering Changes

### Responsive sizing — preserve aspect ratio

The party room outer container uses:

```css
width: min(95vw, 1000px);
aspect-ratio: 800 / 500;  /* = worldSize.width / worldSize.height */
```

Inside, the floor `<div>` fills its parent (`width: 100%; height: 100%`). All zone, wall, and avatar positioning becomes **percent-based** rather than absolute pixels:

- Zone: `left: zone.x%`, `top: zone.y%`, `width: zone.width%`, `height: zone.height%` (interpreted from the existing logical-coord percentages already in seed data — except now treating them as box top-left and box dimensions, matching the new boxy rendering).
  - **Coordinate convention change:** zones move from center-anchored to **top-left anchored**. The Phase 1 seed values were center-based; the Phase 2 schema is top-left. The Cream Terrazzo seed data is rewritten with new values that produce the same visual placement under the new convention.
- Wall: `left: wall.x%`, `top: wall.y%`, `width: wall.width%`, `height: wall.height%`.
- Avatar: `left: calc((position.x / worldWidth) * 100%)`, `top: calc((position.y / worldHeight) * 100%)`, with a `transform: translate(-50%, -50%)` centering offset.

### Click coordinate handling

`PartySpace.onClick` reads the floor's `getBoundingClientRect()`, computes `(clientX - rect.left) / rect.width * worldWidth` and `(clientY - rect.top) / rect.height * worldHeight`. The logical world stays 800×500 internally, so movement physics and AI-agent reasoning are unchanged.

### `clipPath` on the room

When `room.clipPath` is set, the floor `<div>` uses `clip-path: <value>`. Default is `none` (rectangle). The outer wall border is still drawn via `border` — when a `clipPath` cuts off part of the rectangle, the border follows the rectangle and the clipped-off region simply doesn't render. That's acceptable for v1; rendering a true polygonal border is out of scope.

### Interior wall stubs

Each `Wall` renders as an absolutely-positioned `<div>` with `background: wall.color`, sized via percent of the floor. Stubs are **decorative only** — they do not block movement (collision is out of scope for steps 1–2 per CLAUDE.md).

---

## Lobby Preview

Extract a `PartyPreview` component used by both the Lobby card and (future) any other place that needs a non-interactive thumbnail:

```typescript
// frontend/src/components/PartyPreview.tsx
type Props = { party: PartyConfig };

// Renders the floor with theme, room outline, walls, and boxy zones at
// the preview's natural size (width: 100%; aspect-ratio: 800/500).
// No avatar, no music pill, no click handler.
```

The Lobby card uses `<PartyPreview party={p} />` in place of the current colored swatch `<div>`.

---

## Mobile-friendly Forms

### SignIn

- `main` container: `max-width: min(420px, 92vw)`, `padding: clamp(16px, 4vw, 24px)`, `margin: clamp(24px, 8vh, 64px) auto`.
- `h1` font-size: `clamp(20px, 5vw, 28px)`.
- Color grid keeps `repeat(6, 1fr)` columns — at 92vw on a small phone (~360px wide), each swatch is ~50px which is touch-friendly.

### Lobby

- `main` container: `max-width: min(1100px, 92vw)`, `padding: clamp(16px, 4vw, 24px)`.
- Grid `gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))'` so on a phone (~360px) you get one card full-width and on a tablet two; laptop fits 3–4.
- `h1` font-size: `clamp(22px, 5vw, 32px)`.

### Party

- Outer `main` `padding: clamp(8px, 2vw, 16px)`.
- Header `flex-wrap: wrap` so the "Leave party" button drops to a second line on phone if needed.
- The party-room container handles its own responsive sizing as described above.

No CSS media queries; we lean on `clamp()` and `min()` for fluid scaling. This avoids breakpoint thrash.

---

## Testing

Update existing tests to reflect the new schema, and add focused tests for the new behaviors:

- **Backend `test_models.py`**: extend `test_party_config_minimum_shape` to include a `room` value. Add a test that `room.clipPath` accepts `null` and a string. Add a test for the new `Wall` model.
- **Backend `test_parties_data.py`**: assert `CREAM_TERRAZZO.room.walls` has 2 wall stubs and `room.border` is set.
- **Frontend `registry.contract.test.ts`**: extend to assert the local TS registry's `room` shape matches the new fields.
- **Frontend `PartyPreview.test.tsx`** (new): renders a card with the floor color and one zone box; does NOT render an avatar.
- **Frontend `Party.test.tsx`**: update mock party payload to include `room`; assert wall stubs render with the correct background color (one test per wall).
- **Frontend `Zone.test.tsx`** (new): renders a Zone with the boxy filled style — assert `data-testid="zone-{id}"` exists and computed style has the expected `border` substring.

The `useMovement` test stays as-is — logical coordinates are unchanged, and the hook never touched DOM rendering.

---

## Out of Scope

- Polygonal outer border rendering when `clipPath` is set (the inner clip works; an SVG-rendered border is deferred).
- Wall collision (still no collision for any object).
- A new party with a different `clipPath` — schema supports it but seed data adds only Cream Terrazzo's rectangle. Adding new parties is its own follow-up.
- Color-scheme customization of forms or theming the lobby.

---

## Decisions & Rationale

| Decision | Why |
|---|---|
| `Room` as a sub-object on `PartyConfig` | Keeps room-specific fields grouped; future parties extend without polluting top-level fields. |
| `clipPath` as raw CSS string | Maximum expressiveness with minimum complexity. We could have used a named shape enum but every new shape would mean a code change. |
| Zone coord convention switch to top-left anchored | Boxy zones are easier to author when you think "rect from here to here" than "center plus dimensions." Existing seed data is rewritten. |
| `clamp()` instead of media queries | Fluid scaling avoids ugly snap-points and is simpler. Forms are small enough not to need true breakpoint layouts. |
| Walls are decorative (no collision) | Phase 1–2 don't have collision for anything. Adding it for walls only would be inconsistent. |
| `PartyPreview` as a separate component | Reused by Lobby today; reusable for any thumbnail need later (party picker grid in a sidebar, an in-game minimap, etc). |
