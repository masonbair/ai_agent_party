import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useMovement } from '../src/hooks/useMovement';

function setupRaf() {
  let frame = 0;
  const cbs = new Map<number, FrameRequestCallback>();
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
    frame += 1;
    cbs.set(frame, cb);
    return frame;
  });
  vi.stubGlobal('cancelAnimationFrame', (id: number) => {
    cbs.delete(id);
  });
  return {
    tick(times = 1, ms = 16) {
      for (let i = 0; i < times; i++) {
        const next = cbs.size > 0 ? Math.min(...cbs.keys()) : null;
        if (next == null) return;
        const cb = cbs.get(next)!;
        cbs.delete(next);
        cb(performance.now() + ms * (i + 1));
      }
    },
  };
}

describe('useMovement', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('moves right when "d" is held', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 800, worldHeight: 500, speed: 200 }),
    );

    const startX = result.current.position.x;
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }));
      raf.tick(3);
    });
    expect(result.current.position.x).toBeGreaterThan(startX);
  });

  it('moves right when "ArrowRight" is held', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 800, worldHeight: 500, speed: 200 }),
    );

    const startX = result.current.position.x;
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
      raf.tick(3);
    });
    expect(result.current.position.x).toBeGreaterThan(startX);
  });

  it('clamps position at world bounds', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 100, worldHeight: 100, speed: 9999 }),
    );

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }));
      raf.tick(20);
    });
    expect(result.current.position.x).toBeLessThanOrEqual(100);
    expect(result.current.position.x).toBeGreaterThanOrEqual(0);
  });

  it('moves toward a click target', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 800, worldHeight: 500, speed: 400 }),
    );

    act(() => {
      result.current.setTarget({ x: 700, y: 400 });
      raf.tick(5);
    });
    expect(result.current.position.x).toBeGreaterThan(0);
    expect(result.current.position.y).toBeGreaterThan(0);
  });

  it('cancels active target when a WASD key is pressed', () => {
    const raf = setupRaf();
    const { result } = renderHook(() =>
      useMovement({ worldWidth: 800, worldHeight: 500, speed: 100 }),
    );

    act(() => {
      result.current.setTarget({ x: 700, y: 400 });
      raf.tick(2);
    });
    const xAfterClickStart = result.current.position.x;

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
      window.dispatchEvent(new KeyboardEvent('keyup', { key: 'a' }));
      raf.tick(2);
    });
    expect(result.current.target).toBeNull();
    expect(result.current.position.x).toBeLessThanOrEqual(xAfterClickStart + 1);
  });

  it('does not enter a wall when WASD pushes into it', () => {
    const raf = setupRaf();
    // Wall covers x>=50% (i.e. logical x>=400) of an 800x500 world.
    const walls = [{ x: 50, y: 0, width: 50, height: 100, color: '#000' }];
    const { result } = renderHook(() =>
      useMovement({
        worldWidth: 800,
        worldHeight: 500,
        speed: 1000,
        walls,
        start: { x: 100, y: 250 },
      }),
    );

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }));
      raf.tick(40);
    });
    // Avatar (radius 14) should not enter the wall: x must stay < 400 - 14 = 386.
    expect(result.current.position.x).toBeLessThanOrEqual(386);
  });

  it('slides along a wall when clicking past it', () => {
    const raf = setupRaf();
    // Vertical wall stub at x=50% (400 in logical), height 60% (300), from y=0 to y=300.
    const walls = [{ x: 50, y: 0, width: 1, height: 60, color: '#000' }];
    const { result } = renderHook(() =>
      useMovement({
        worldWidth: 800,
        worldHeight: 500,
        speed: 400,
        walls,
        start: { x: 200, y: 100 },
      }),
    );

    act(() => {
      // Click target is on the other side of the wall, lower than the stub.
      result.current.setTarget({ x: 700, y: 450 });
      raf.tick(80);
    });

    // After enough ticks, the avatar should have crossed past the wall (x > 420).
    expect(result.current.position.x).toBeGreaterThan(420);
  });
});
