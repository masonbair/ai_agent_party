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

const AVATAR_RADIUS = 14;

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

export function useMovement(opts: Options) {
  const { worldWidth, worldHeight, speed } = opts;
  const [position, setPosition] = useState<Point>(
    opts.start ?? { x: worldWidth / 2, y: worldHeight / 2 },
  );
  const [target, setTargetState] = useState<Point | null>(null);

  const keysRef = useRef<Set<string>>(new Set());
  const targetRef = useRef<Point | null>(null);
  const posRef = useRef<Point>(position);
  const lastTimeRef = useRef<number | null>(null);
  const wallsRef = useRef<Rect[]>(inflateWalls(opts.walls, worldWidth, worldHeight));

  posRef.current = position;
  targetRef.current = target;
  wallsRef.current = inflateWalls(opts.walls, worldWidth, worldHeight);

  function setTarget(p: Point | null) {
    targetRef.current = p;
    setTargetState(p);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const key = e.key.toLowerCase();
      if (KEY_TO_DIR[key]) {
        keysRef.current.add(key);
        if (targetRef.current !== null) {
          targetRef.current = null;
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
        if (dist < 1) {
          targetRef.current = null;
          setTargetState(null);
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
        // Try X-only slide.
        if (!isBlocked({ x: nx, y }, rects)) {
          ny = y;
        } else if (!isBlocked({ x, y: ny }, rects)) {
          // Y-only slide.
          nx = x;
        } else {
          // Stuck — no movement this frame.
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
