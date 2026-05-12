import { useEffect, useRef, useState } from 'react';

export type Point = { x: number; y: number };

type Options = {
  worldWidth: number;
  worldHeight: number;
  speed: number; // logical units per second
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

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
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

  posRef.current = position;
  targetRef.current = target;

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

      let { x, y } = posRef.current;
      let moved = false;

      if (keysRef.current.size > 0) {
        let dx = 0;
        let dy = 0;
        for (const k of keysRef.current) {
          const dir = KEY_TO_DIR[k];
          dx += dir.x;
          dy += dir.y;
        }
        const len = Math.hypot(dx, dy);
        if (len > 0) {
          x += (dx / len) * speed * dt;
          y += (dy / len) * speed * dt;
          moved = true;
        }
      } else if (targetRef.current) {
        const t = targetRef.current;
        const dx = t.x - x;
        const dy = t.y - y;
        const dist = Math.hypot(dx, dy);
        if (dist < 1) {
          targetRef.current = null;
          setTargetState(null);
        } else {
          const step = Math.min(dist, speed * dt);
          x += (dx / dist) * step;
          y += (dy / dist) * step;
          moved = true;
        }
      }

      if (moved) {
        const next = {
          x: clamp(x, 0, worldWidth),
          y: clamp(y, 0, worldHeight),
        };
        posRef.current = next;
        setPosition(next);
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
