# Phase 3 — Collision & Polish Plan

> Use superpowers:subagent-driven-development to execute this plan.

**Goal:** Rename to openParty, polish SignIn and Leave button, add wall collision with sliding (which doubles as minimal pathfinding for click-to-move).

**Spec:** `docs/superpowers/specs/2026-05-12-phase3-collision-and-polish.md`

---

## Task 1: Rename to openParty

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/src/pages/SignIn.tsx`

- [ ] **Step 1:** In `frontend/index.html`, change `<title>ai_agent_party</title>` to `<title>openParty</title>`.

- [ ] **Step 2:** In `frontend/src/pages/SignIn.tsx`, change `<h1>Welcome to ai_agent_party</h1>` to `<h1>Welcome to openParty</h1>`.

- [ ] **Step 3:** Run `cd frontend && npm test` — all tests must pass. The existing SignIn tests don't assert on the h1 text, so this is a safe rename.

- [ ] **Step 4:** Commit:
```bash
git add frontend/index.html frontend/src/pages/SignIn.tsx
git commit -m "feat(frontend): rename app to openParty"
```

---

## Task 2: SignIn visual polish

**Files:**
- Modify: `frontend/src/pages/SignIn.tsx`

The file already uses clamp-based responsive styles. This task adds card styling, a tagline, fancier swatches, and a pill-shaped submit button. All existing tests stay green.

- [ ] **Step 1: Replace the `return (...)` block of `SignIn.tsx`** with:

```tsx
  return (
    <main
      style={{
        maxWidth: 'min(440px, 92vw)',
        margin: 'clamp(24px, 8vh, 80px) auto',
        padding: 'clamp(20px, 4vw, 32px)',
        background: '#fff',
        border: '1px solid #f0e6d8',
        borderRadius: 16,
        boxShadow: '0 10px 30px rgba(0,0,0,0.08)',
      }}
    >
      <h1 style={{ fontSize: 'clamp(24px, 6vw, 36px)', margin: 0, color: '#1a1a1a' }}>
        Welcome to openParty
      </h1>
      <p style={{ margin: '6px 0 24px', color: '#666', fontSize: 'clamp(13px, 3.5vw, 15px)' }}>
        Throw parties with humans and AI agents.
      </p>

      <form onSubmit={onSubmit}>
        <label
          htmlFor="username"
          style={{ display: 'block', marginTop: 8, fontWeight: 600, fontSize: 14 }}
        >
          Username
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
          maxLength={20}
          style={{
            width: '100%',
            padding: '10px 12px',
            marginTop: 6,
            border: '1px solid #ddd',
            borderRadius: 8,
            fontSize: 16,
          }}
        />
        {usernameTouched && !usernameValid && (
          <p style={{ color: '#b00020', fontSize: 13, marginTop: 6 }}>
            Use 2–20 letters and numbers only.
          </p>
        )}

        <fieldset style={{ marginTop: 20, border: 'none', padding: 0 }}>
          <legend style={{ fontWeight: 600, fontSize: 14, marginBottom: 8 }}>
            Favorite color
          </legend>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
            {ALLOWED_COLORS.map((c) => {
              const selected = color === c;
              return (
                <label
                  key={c}
                  style={{
                    display: 'inline-flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                  }}
                >
                  <input
                    type="radio"
                    name="color"
                    value={c}
                    checked={selected}
                    onChange={() => setColor(c)}
                    style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
                  />
                  <span
                    aria-hidden
                    style={{
                      display: 'inline-flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      width: 40,
                      height: 40,
                      borderRadius: '50%',
                      background: c,
                      color: '#fff',
                      fontWeight: 700,
                      transform: selected ? 'scale(1.1)' : 'scale(1)',
                      outline: selected ? '3px solid #333' : '2px solid rgba(0,0,0,0.06)',
                      outlineOffset: 2,
                      transition: 'transform 120ms ease, outline-color 120ms ease',
                      cursor: 'pointer',
                    }}
                  >
                    {selected ? '✓' : ''}
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        {serverError && (
          <p
            role="alert"
            style={{
              color: '#b00020',
              marginTop: 14,
              fontSize: 14,
              background: '#fdecef',
              padding: '8px 12px',
              borderRadius: 8,
            }}
          >
            {serverError}
          </p>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          style={{
            marginTop: 24,
            width: '100%',
            padding: '12px 20px',
            background: canSubmit ? '#ff6b9d' : '#f0c7d6',
            color: '#fff',
            border: 'none',
            borderRadius: 999,
            fontSize: 16,
            fontWeight: 600,
            cursor: canSubmit ? 'pointer' : 'not-allowed',
            boxShadow: canSubmit ? '0 4px 10px rgba(255,107,157,0.30)' : 'none',
            transition: 'transform 120ms ease, box-shadow 120ms ease',
          }}
        >
          Enter
        </button>
      </form>
    </main>
  );
```

- [ ] **Step 2:** Run `cd frontend && npm test` — all 24 tests still pass (SignIn assertions only look for `getByRole('button', {name: /enter/i})`, `getByLabelText(/username/i)`, `getAllByRole('radio')`, and the lobby redirect — all still valid).

- [ ] **Step 3:** Commit:
```bash
git add frontend/src/pages/SignIn.tsx
git commit -m "feat(frontend): polish SignIn with card style and tagline"
```

---

## Task 3: Leave-party button polish

**Files:**
- Modify: `frontend/src/pages/Party.tsx`

- [ ] **Step 1:** In `Party.tsx`, locate the `<header>` block. Replace it with:

```tsx
      <header
        style={{
          padding: 'clamp(8px, 2vw, 16px) clamp(12px, 3vw, 24px)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h1 style={{ margin: 0, fontSize: 'clamp(20px, 4vw, 28px)' }}>{party.name}</h1>
        <button
          type="button"
          onClick={() => navigate('/lobby')}
          style={{
            background: party.theme.accent,
            color: '#fff',
            border: 'none',
            padding: '8px 16px',
            borderRadius: 999,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            boxShadow: '0 2px 6px rgba(0,0,0,0.10)',
            transition: 'transform 120ms ease, box-shadow 120ms ease',
          }}
        >
          ← Leave party
        </button>
      </header>
```

- [ ] **Step 2:** Run `cd frontend && npm test` — all tests pass.

- [ ] **Step 3:** Commit:
```bash
git add frontend/src/pages/Party.tsx
git commit -m "feat(frontend): polish Leave party button"
```

---

## Task 4: Wall collision in useMovement (TDD)

**Files:**
- Modify: `frontend/src/hooks/useMovement.ts`
- Modify: `frontend/tests/useMovement.test.ts`

- [ ] **Step 1: Add failing tests**

Append the following two `it` blocks at the end of the `describe('useMovement', ...)` block in `frontend/tests/useMovement.test.ts` (immediately before the closing `});` of the describe):

```typescript
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
```

- [ ] **Step 2:** Run `cd frontend && npm test -- useMovement`. Both new tests should FAIL because there is no collision yet.

- [ ] **Step 3: Implement collision**

Replace `frontend/src/hooks/useMovement.ts` entirely with:

```typescript
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
```

- [ ] **Step 4:** Run `cd frontend && npm test -- useMovement`. Expect all useMovement tests pass (5 existing + 2 new = 7).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useMovement.ts frontend/tests/useMovement.test.ts
git commit -m "feat(frontend): wall collision with slide for WASD and click-to-move"
```

---

## Task 5: Wire walls into PartySpace

**Files:**
- Modify: `frontend/src/components/PartySpace.tsx`

- [ ] **Step 1:** In `PartySpace.tsx`, update the `useMovement` call to pass walls:

```tsx
  const { position, setTarget } = useMovement({
    worldWidth: width,
    worldHeight: height,
    speed: SPEED,
    walls: party.room.walls,
  });
```

- [ ] **Step 2:** Run `cd frontend && npm test`. All tests pass.

- [ ] **Step 3:** Commit:
```bash
git add frontend/src/components/PartySpace.tsx
git commit -m "feat(frontend): pass party walls to useMovement for collision"
```

---

## Task 6: Full verification

- [ ] **Step 1:** `cd backend && source .venv/bin/activate && pytest -v` — all pass.
- [ ] **Step 2:** `cd frontend && npm test` — all pass.
- [ ] **Step 3:** `cd frontend && npm run build` — clean build.
- [ ] **Step 4:** Browser smoke (you, the user):
  - Visit `/` — see card UI with "Welcome to openParty" + tagline, polished swatches, pill-shaped pink "Enter" button.
  - Tab title is "openParty".
  - On phone width, card stays readable, button is full-width.
  - In the party page, click "← Leave party" — pill-shaped, accent-colored.
  - Walk into the vertical wall stub between dance and chill: avatar stops, can slide up or down along the wall.
  - Click on the far side of the wall: avatar lerps, slides along the wall edge, then continues to the click target.
