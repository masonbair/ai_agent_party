import { useEffect, useRef, useState } from 'react';

export type Point = { x: number; y: number };

export type MovementWall = {
  x: number;       // % of world width
  y: number;       // % of world height
  width: number;
  height: number;
};

type Options = {
  worldWidth: number;
  worldHeight: number;
  speed: number;
  walls?: MovementWall[];
  start?: Point;
};

const KEY_TO_DIR: Record<string, Point> = {
  w: { x: 0, y: -1 },
  a: { x: -1, y: 0 },
  s: { x: 0, y: 1 },
  d: { x: 1, y: 0 },
  arrowup: { x: 0, y: -1 },
  arrowleft: { x: -1, y: 0 },
  arrowdown: { x: 0, y: 1 },
  arrowright: { x: 1, y: 0 },
};

// Keep in sync with AVATAR_RADIUS in backend/app/collision.py.
const AVATAR_RADIUS = 14;
const DETOUR_MARGIN = 2;
const WAYPOINT_REACHED_DIST = 4;
const TARGET_REACHED_DIST = 1;
const MAX_DETOUR_ITERATIONS = 4;

type Rect = { left: number; top: number; right: number; bottom: number };

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function inflateWalls(
  walls: MovementWall[] | undefined,
  worldWidth: number,
  worldHeight: number,
): Rect[] {
  if (!walls) return [];
  return walls.map((w) => {
    const left = (w.x / 100) * worldWidth - AVATAR_RADIUS;
    const top = (w.y / 100) * worldHeight - AVATAR_RADIUS;
    const right = ((w.x + w.width) / 100) * worldWidth + AVATAR_RADIUS;
    const bottom = ((w.y + w.height) / 100) * worldHeight + AVATAR_RADIUS;
    return { left, top, right, bottom };
  });
}

function isBlocked(p: Point, rects: Rect[]): boolean {
  for (const r of rects) {
    if (p.x > r.left && p.x < r.right && p.y > r.top && p.y < r.bottom) {
      return true;
    }
  }
  return false;
}

// True if the segment from A to B passes through the interior of `r`.
function segmentCrossesRect(A: Point, B: Point, r: Rect): boolean {
  const dx = B.x - A.x;
  const dy = B.y - A.y;

  let tMinX = 0;
  let tMaxX = 1;
  if (dx === 0) {
    if (A.x <= r.left || A.x >= r.right) return false;
  } else {
    const t1 = (r.left - A.x) / dx;
    const t2 = (r.right - A.x) / dx;
    tMinX = Math.min(t1, t2);
    tMaxX = Math.max(t1, t2);
  }

  let tMinY = 0;
  let tMaxY = 1;
  if (dy === 0) {
    if (A.y <= r.top || A.y >= r.bottom) return false;
  } else {
    const t1 = (r.top - A.y) / dy;
    const t2 = (r.bottom - A.y) / dy;
    tMinY = Math.min(t1, t2);
    tMaxY = Math.max(t1, t2);
  }

  const tStart = Math.max(tMinX, tMinY, 0);
  const tEnd = Math.min(tMaxX, tMaxY, 1);
  return tStart < tEnd;
}

// Plan a 2-step detour around `wall` from `from` toward `to`.
// Chooses whichever corner (top/bottom for tall walls, left/right for wide ones)
// is closer to `from`, falling back to the opposite corner if the preferred
// one would be outside the world.
function planDetour(
  from: Point,
  to: Point,
  wall: Rect,
  worldWidth: number,
  worldHeight: number,
): Point[] {
  const wallWidth = wall.right - wall.left;
  const wallHeight = wall.bottom - wall.top;
  if (wallHeight >= wallWidth) {
    let goUp = Math.abs(from.y - wall.top) < Math.abs(from.y - wall.bottom);
    const topCornerY = wall.top - DETOUR_MARGIN;
    const bottomCornerY = wall.bottom + DETOUR_MARGIN;
    if (goUp && topCornerY < 0) goUp = false;
    else if (!goUp && bottomCornerY > worldHeight) goUp = true;
    const cornerY = goUp ? topCornerY : bottomCornerY;
    const exitX =
      to.x > wall.right ? wall.right + DETOUR_MARGIN : wall.left - DETOUR_MARGIN;
    return [
      { x: from.x, y: cornerY },
      { x: exitX, y: cornerY },
    ];
  }
  let goLeft = Math.abs(from.x - wall.left) < Math.abs(from.x - wall.right);
  const leftCornerX = wall.left - DETOUR_MARGIN;
  const rightCornerX = wall.right + DETOUR_MARGIN;
  if (goLeft && leftCornerX < 0) goLeft = false;
  else if (!goLeft && rightCornerX > worldWidth) goLeft = true;
  const cornerX = goLeft ? leftCornerX : rightCornerX;
  const exitY =
    to.y > wall.bottom ? wall.bottom + DETOUR_MARGIN : wall.top - DETOUR_MARGIN;
  return [
    { x: cornerX, y: from.y },
    { x: cornerX, y: exitY },
  ];
}

// Build a list of waypoints (ending at `to`) that avoids any wall whose
// interior the direct line would otherwise cross.
function planPath(
  from: Point,
  to: Point,
  rects: Rect[],
  worldWidth: number,
  worldHeight: number,
): Point[] {
  const waypoints: Point[] = [];
  let current = from;
  for (let i = 0; i < MAX_DETOUR_ITERATIONS; i++) {
    let crossing: Rect | null = null;
    for (const r of rects) {
      if (segmentCrossesRect(current, to, r)) {
        crossing = r;
        break;
      }
    }
    if (!crossing) break;
    const detour = planDetour(current, to, crossing, worldWidth, worldHeight);
    waypoints.push(...detour);
    current = detour[detour.length - 1];
  }
  waypoints.push(to);
  return waypoints;
}

export function useMovement(opts: Options) {
  const { worldWidth, worldHeight, speed } = opts;
  const [position, setPosition] = useState<Point>(
    opts.start ?? { x: worldWidth / 2, y: worldHeight / 2 },
  );
  const [target, setTargetState] = useState<Point | null>(null);

  const keysRef = useRef<Set<string>>(new Set());
  const targetRef = useRef<Point | null>(null);
  const waypointQueueRef = useRef<Point[]>([]);
  const posRef = useRef<Point>(position);
  const lastTimeRef = useRef<number | null>(null);
  const wallsRef = useRef<Rect[]>(inflateWalls(opts.walls, worldWidth, worldHeight));

  posRef.current = position;
  targetRef.current = target;
  wallsRef.current = inflateWalls(opts.walls, worldWidth, worldHeight);

  function setTarget(p: Point | null) {
    if (p === null) {
      waypointQueueRef.current = [];
      targetRef.current = null;
      setTargetState(null);
      return;
    }
    const path = planPath(posRef.current, p, wallsRef.current, worldWidth, worldHeight);
    const first = path[0];
    waypointQueueRef.current = path.slice(1);
    targetRef.current = first;
    setTargetState(first);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const key = e.key.toLowerCase();
      if (KEY_TO_DIR[key]) {
        keysRef.current.add(key);
        if (targetRef.current !== null) {
          targetRef.current = null;
          waypointQueueRef.current = [];
          setTargetState(null);
        }
      }
    }
    function onKeyUp(e: KeyboardEvent) {
      keysRef.current.delete(e.key.toLowerCase());
    }
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
    };
  }, []);

  useEffect(() => {
    let rafId = 0;
    function loop(now: number) {
      const last = lastTimeRef.current;
      const dt = last == null ? 0 : (now - last) / 1000;
      lastTimeRef.current = now;

      const { x, y } = posRef.current;
      let dx = 0;
      let dy = 0;

      if (keysRef.current.size > 0) {
        for (const k of keysRef.current) {
          const dir = KEY_TO_DIR[k];
          dx += dir.x;
          dy += dir.y;
        }
        const len = Math.hypot(dx, dy);
        if (len > 0) {
          dx = (dx / len) * speed * dt;
          dy = (dy / len) * speed * dt;
        }
      } else if (targetRef.current) {
        const t = targetRef.current;
        const tdx = t.x - x;
        const tdy = t.y - y;
        const dist = Math.hypot(tdx, tdy);
        const reachThreshold =
          waypointQueueRef.current.length > 0
            ? WAYPOINT_REACHED_DIST
            : TARGET_REACHED_DIST;
        if (dist < reachThreshold) {
          if (waypointQueueRef.current.length > 0) {
            const next = waypointQueueRef.current.shift()!;
            targetRef.current = next;
            setTargetState(next);
          } else {
            targetRef.current = null;
            setTargetState(null);
          }
        } else {
          const step = Math.min(dist, speed * dt);
          dx = (tdx / dist) * step;
          dy = (tdy / dist) * step;
        }
      }

      if (dx === 0 && dy === 0) {
        rafId = requestAnimationFrame(loop);
        return;
      }

      const rects = wallsRef.current;
      let nx = x + dx;
      let ny = y + dy;

      if (isBlocked({ x: nx, y: ny }, rects)) {
        if (!isBlocked({ x: nx, y }, rects)) {
          ny = y;
        } else if (!isBlocked({ x, y: ny }, rects)) {
          nx = x;
        } else {
          nx = x;
          ny = y;
        }
      }

      const clamped = {
        x: clamp(nx, 0, worldWidth),
        y: clamp(ny, 0, worldHeight),
      };
      if (clamped.x !== x || clamped.y !== y) {
        posRef.current = clamped;
        setPosition(clamped);
      }
      rafId = requestAnimationFrame(loop);
    }
    rafId = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(rafId);
      lastTimeRef.current = null;
    };
  }, [worldWidth, worldHeight, speed]);

  return { position, target, setTarget };
}
