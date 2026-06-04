// Anti-overlap layout for chat bubbles. Bubbles are anchored above their
// speaker's avatar; when two speakers stand close together their bubbles
// would overlap, so we lift later ones by whole "levels". Coordinates are in
// world units (same space as avatar x/y).

export type BubbleAnchor = { id: string; x: number; y: number };

// Two bubbles conflict when their anchors are near in both axes. Tuned to the
// bubble's on-screen footprint (~maxWidth 260px / ~2 lines) in world units.
const X_OVERLAP = 150;
const Y_OVERLAP = 60;
export const LEVEL_HEIGHT_PX = 34;

export function computeBubbleOffsets(
  anchors: BubbleAnchor[],
): Record<string, number> {
  // Process top-to-bottom so upper bubbles take the base row and lower,
  // later ones stack upward above them — deterministic and stable.
  const ordered = [...anchors].sort((a, b) => a.y - b.y || a.id.localeCompare(b.id));
  const placed: { x: number; y: number; level: number }[] = [];
  const offsets: Record<string, number> = {};

  for (const a of ordered) {
    let level = 0;
    // Bump the level until this bubble no longer collides with an
    // already-placed bubble occupying the same level near the same spot.
    let collides = true;
    while (collides) {
      collides = placed.some(
        (p) =>
          p.level === level &&
          Math.abs(p.x - a.x) < X_OVERLAP &&
          Math.abs(p.y - a.y) < Y_OVERLAP,
      );
      if (collides) level += 1;
    }
    placed.push({ x: a.x, y: a.y, level });
    offsets[a.id] = level * LEVEL_HEIGHT_PX;
  }
  return offsets;
}
