# Phase 2 — Room Shape, Boxy Zones, Responsive Layout, Lobby Previews Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Implement the visual + responsiveness polish per `docs/superpowers/specs/2026-05-12-phase2-room-shape-and-responsive.md`.

**Architecture:** Schema-additive — both backend pydantic and frontend TS gain new `Room`, `Wall` types and a `borderColor` on `Zone`. Zone renders as a boxy filled rect. Party room scales with `min(95vw, 1000px)` + `aspect-ratio`. Lobby uses a new `PartyPreview` component. Forms use `clamp()` for fluid scaling.

**Spec:** `docs/superpowers/specs/2026-05-12-phase2-room-shape-and-responsive.md`

---

## File Structure

**Backend modify:**
- `backend/app/models.py` — add `Wall`, `Room`; add `borderColor` to `Zone`; add `room` to `PartyConfig`.
- `backend/app/parties_data.py` — populate `CREAM_TERRAZZO.room`, new zone coords (top-left anchored), `borderColor` on each zone.
- `backend/tests/test_models.py` — extend.
- `backend/tests/test_parties_data.py` — extend.

**Frontend modify:**
- `frontend/src/api/types.ts` — add `Wall`, `Room`; add `borderColor` to `Zone`; add `room` to `PartyConfig`.
- `frontend/src/parties/cream-terrazzo.ts` — new seed values matching backend.
- `frontend/src/components/Zone.tsx` — boxy rendering, percent-based positioning.
- `frontend/src/components/PartySpace.tsx` — responsive container, percent-based avatar, walls, click→logical-coord conversion.
- `frontend/src/components/Avatar.tsx` — percent-based positioning.
- `frontend/src/pages/SignIn.tsx` — `clamp()` styles.
- `frontend/src/pages/Lobby.tsx` — `clamp()` styles, use `PartyPreview`.
- `frontend/src/pages/Party.tsx` — minor responsive tweaks.
- `frontend/tests/Party.test.tsx` — update mock to include `room`, assert wall renders.
- `frontend/tests/registry.contract.test.ts` — extend.

**Frontend create:**
- `frontend/src/components/Wall.tsx` — render one wall stub.
- `frontend/src/components/PartyPreview.tsx` — non-interactive mini room.
- `frontend/tests/PartyPreview.test.tsx`.
- `frontend/tests/Zone.test.tsx`.

---

## Task 1: Backend schema additions

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Update the failing test**

Edit `backend/tests/test_models.py`. Add at the top of the imports:

```python
from app.models import (
    CreateSessionRequest,
    PartyConfig,
    Room,
    User,
    Wall,
    Zone,
)
```

Replace the `test_party_config_minimum_shape` function with:

```python
def test_party_config_minimum_shape() -> None:
    zone = Zone(
        id="dance",
        label="DANCE",
        x=8.0,
        y=10.0,
        width=34.0,
        height=36.0,
        color="#ff6b9d",
        labelColor="#ffffff",
        borderColor="#8b1a4a",
    )
    cfg = PartyConfig(
        slug="cream-terrazzo",
        name="Cream Terrazzo Lounge",
        description="A bright, friendly party.",
        theme={"floor": "cream", "accent": "#ff6b9d"},
        zones=[zone],
        music={"url": None, "label": "Music coming soon"},
        worldSize={"width": 800, "height": 500},
        room={
            "clipPath": None,
            "border": "6px solid #8b6f47",
            "borderRadius": 12,
            "walls": [
                {"x": 50.0, "y": 0.0, "width": 0.75, "height": 30.0, "color": "#8b6f47"}
            ],
        },
    )
    assert cfg.slug == "cream-terrazzo"
    assert cfg.zones[0].borderColor == "#8b1a4a"
    assert cfg.room.border.startswith("6px")
    assert len(cfg.room.walls) == 1


def test_room_allows_no_walls_and_no_clip_path() -> None:
    room = Room(clipPath=None, border="2px solid black", walls=[])
    assert room.clipPath is None
    assert room.borderRadius is None
    assert room.walls == []


def test_room_accepts_clip_path_string() -> None:
    room = Room(
        clipPath="polygon(0 0, 100% 0, 100% 100%, 0 100%)",
        border="2px solid black",
        walls=[],
    )
    assert "polygon" in room.clipPath


def test_wall_validates_dimensions() -> None:
    w = Wall(x=10.0, y=20.0, width=5.0, height=0.75, color="#000000")
    assert w.x == 10.0
```

- [ ] **Step 2: Run — verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models.py -v`
Expected: FAIL — `ImportError` on `Room`/`Wall` and `ValidationError` on `borderColor` and `room` field missing.

- [ ] **Step 3: Implement models**

Edit `backend/app/models.py`. Add `borderColor` to `Zone`:

```python
class Zone(BaseModel):
    id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    color: str
    labelColor: str
    borderColor: str
```

Add `Wall` and `Room`:

```python
class Wall(BaseModel):
    x: float
    y: float
    width: float
    height: float
    color: str


class Room(BaseModel):
    clipPath: str | None = None
    border: str
    borderRadius: int | None = None
    walls: list[Wall]
```

Update `PartyConfig` to include `room: Room`:

```python
class PartyConfig(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    description: str
    theme: Theme
    zones: list[Zone]
    music: Music
    worldSize: WorldSize
    room: Room
```

- [ ] **Step 4: Run — verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_models.py -v`
Expected: all tests pass (existing 7 + the 3 new = 10 in this file).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(backend): add Room/Wall models and Zone.borderColor"
```

---

## Task 2: Backend Cream Terrazzo seed data

**Files:**
- Modify: `backend/app/parties_data.py`
- Modify: `backend/tests/test_parties_data.py`

- [ ] **Step 1: Update the failing test**

Edit `backend/tests/test_parties_data.py`. Replace its contents with:

```python
from app.parties_data import CREAM_TERRAZZO


def test_cream_terrazzo_has_expected_slug_and_zones() -> None:
    assert CREAM_TERRAZZO.slug == "cream-terrazzo"
    zone_ids = {z.id for z in CREAM_TERRAZZO.zones}
    assert zone_ids == {"dance", "chill", "snacks"}


def test_cream_terrazzo_music_is_placeholder() -> None:
    assert CREAM_TERRAZZO.music.url is None
    assert "coming soon" in CREAM_TERRAZZO.music.label.lower()


def test_cream_terrazzo_room_has_walls_and_border() -> None:
    room = CREAM_TERRAZZO.room
    assert room.border.startswith("6px")
    assert room.borderRadius == 12
    assert len(room.walls) == 2
    assert room.clipPath is None


def test_cream_terrazzo_zones_have_solid_fill_colors() -> None:
    # Filled boxes use a solid color (hex or rgb), not rgba with alpha.
    for z in CREAM_TERRAZZO.zones:
        assert z.color.startswith("#"), f"zone {z.id} should use solid hex fill"
        assert z.borderColor.startswith("#")
```

- [ ] **Step 2: Run — verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_parties_data.py -v`
Expected: tests fail because `Zone.borderColor` is missing and `PartyConfig.room` is missing in the current seed.

- [ ] **Step 3: Implement seed update**

Replace the contents of `backend/app/parties_data.py` with:

```python
from app.models import Music, PartyConfig, Room, Theme, Wall, WorldSize, Zone

CREAM_TERRAZZO = PartyConfig(
    slug="cream-terrazzo",
    name="Cream Terrazzo Lounge",
    description="A bright, friendly room with bold pastel zones.",
    theme=Theme(
        floor=(
            "#f4ead5 radial-gradient(circle 2px at 10% 20%, #c0a070 1px, transparent 2px), "
            "radial-gradient(circle 2px at 40% 60%, #a85d3a 1px, transparent 2px), "
            "radial-gradient(circle 2px at 70% 30%, #c0a070 1px, transparent 2px), "
            "radial-gradient(circle 2px at 85% 80%, #8b6f47 1px, transparent 2px), "
            "radial-gradient(circle 2px at 25% 85%, #c0a070 1px, transparent 2px)"
        ),
        accent="#ff6b9d",
    ),
    zones=[
        Zone(
            id="dance",
            label="DANCE",
            x=6.0,
            y=8.0,
            width=34.0,
            height=36.0,
            color="#ff6b9d",
            labelColor="#ffffff",
            borderColor="#8b1a4a",
        ),
        Zone(
            id="chill",
            label="CHILL",
            x=60.0,
            y=8.0,
            width=34.0,
            height=28.0,
            color="#4dd0e1",
            labelColor="#ffffff",
            borderColor="#00606e",
        ),
        Zone(
            id="snacks",
            label="SNACKS",
            x=28.0,
            y=58.0,
            width=44.0,
            height=34.0,
            color="#ffb74d",
            labelColor="#ffffff",
            borderColor="#6b3a00",
        ),
    ],
    music=Music(url=None, label="Music coming soon"),
    worldSize=WorldSize(width=800, height=500),
    room=Room(
        clipPath=None,
        border="6px solid #8b6f47",
        borderRadius=12,
        walls=[
            # Vertical stub between dance and chill, top half.
            Wall(x=50.0, y=0.0, width=0.75, height=30.0, color="#8b6f47"),
            # Horizontal stub on the right above snacks.
            Wall(x=75.0, y=40.0, width=25.0, height=1.2, color="#8b6f47"),
        ],
    ),
)

PARTY_REGISTRY: dict[str, PartyConfig] = {CREAM_TERRAZZO.slug: CREAM_TERRAZZO}
```

- [ ] **Step 4: Run — verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: all backend tests pass (the count goes up by the new tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/parties_data.py backend/tests/test_parties_data.py
git commit -m "feat(backend): seed Cream Terrazzo with room/walls and solid zone colors"
```

---

## Task 3: Frontend type extensions

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/parties/cream-terrazzo.ts`
- Modify: `frontend/tests/registry.contract.test.ts`

- [ ] **Step 1: Update the failing test**

Edit `frontend/tests/registry.contract.test.ts`. Replace its contents with:

```typescript
import { describe, expect, it } from 'vitest';
import { PARTIES } from '../src/parties/registry';

describe('frontend party registry', () => {
  it('includes cream-terrazzo with the three named zones', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo');
    expect(ct).toBeDefined();
    const zoneIds = new Set(ct!.zones.map((z) => z.id));
    expect(zoneIds).toEqual(new Set(['dance', 'chill', 'snacks']));
  });

  it('marks music as a placeholder', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo')!;
    expect(ct.music.url).toBeNull();
  });

  it('defines a room with walls and a border', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo')!;
    expect(ct.room.border).toMatch(/^\d+px /);
    expect(ct.room.walls.length).toBeGreaterThan(0);
  });

  it('every zone has solid fill and a border color', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo')!;
    for (const z of ct.zones) {
      expect(z.color.startsWith('#')).toBe(true);
      expect(z.borderColor.startsWith('#')).toBe(true);
    }
  });
});
```

- [ ] **Step 2: Run — verify it fails**

Run: `cd frontend && npm test -- registry.contract`
Expected: TS errors and/or runtime failures because `Zone.borderColor` and `PartyConfig.room` are missing.

- [ ] **Step 3: Update types**

Edit `frontend/src/api/types.ts`. Replace its contents with:

```typescript
export type User = {
  session_id: string;
  username: string;
  color: string;
};

export type Zone = {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
  labelColor: string;
  borderColor: string;
};

export type Wall = {
  x: number;
  y: number;
  width: number;
  height: number;
  color: string;
};

export type Room = {
  clipPath: string | null;
  border: string;
  borderRadius?: number;
  walls: Wall[];
};

export type PartyConfig = {
  slug: string;
  name: string;
  description: string;
  theme: { floor: string; accent: string };
  zones: Zone[];
  music: { url: string | null; label: string };
  worldSize: { width: number; height: number };
  room: Room;
};

export type PartiesListResponse = {
  parties: PartyConfig[];
};
```

Then update `frontend/src/parties/types.ts` to also re-export `Wall` and `Room`:

```typescript
export type { PartyConfig, Room, Wall, Zone } from '../api/types';
```

- [ ] **Step 4: Update Cream Terrazzo seed**

Replace `frontend/src/parties/cream-terrazzo.ts` with:

```typescript
import type { PartyConfig } from './types';

export const creamTerrazzo: PartyConfig = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room with bold pastel zones.',
  theme: {
    floor:
      '#f4ead5 radial-gradient(circle 2px at 10% 20%, #c0a070 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 40% 60%, #a85d3a 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 70% 30%, #c0a070 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 85% 80%, #8b6f47 1px, transparent 2px), ' +
      'radial-gradient(circle 2px at 25% 85%, #c0a070 1px, transparent 2px)',
    accent: '#ff6b9d',
  },
  zones: [
    {
      id: 'dance',
      label: 'DANCE',
      x: 6.0,
      y: 8.0,
      width: 34.0,
      height: 36.0,
      color: '#ff6b9d',
      labelColor: '#ffffff',
      borderColor: '#8b1a4a',
    },
    {
      id: 'chill',
      label: 'CHILL',
      x: 60.0,
      y: 8.0,
      width: 34.0,
      height: 28.0,
      color: '#4dd0e1',
      labelColor: '#ffffff',
      borderColor: '#00606e',
    },
    {
      id: 'snacks',
      label: 'SNACKS',
      x: 28.0,
      y: 58.0,
      width: 44.0,
      height: 34.0,
      color: '#ffb74d',
      labelColor: '#ffffff',
      borderColor: '#6b3a00',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: {
    clipPath: null,
    border: '6px solid #8b6f47',
    borderRadius: 12,
    walls: [
      { x: 50.0, y: 0.0, width: 0.75, height: 30.0, color: '#8b6f47' },
      { x: 75.0, y: 40.0, width: 25.0, height: 1.2, color: '#8b6f47' },
    ],
  },
};
```

- [ ] **Step 5: Run — verify it passes**

Run: `cd frontend && npm test -- registry.contract`
Expected: 4 tests pass. (The other test files will be broken now because their party mocks lack `room` — that's fixed in later tasks. Run just `registry.contract` for this commit.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/parties/types.ts frontend/src/parties/cream-terrazzo.ts frontend/tests/registry.contract.test.ts
git commit -m "feat(frontend): extend types with Room/Wall, update Cream Terrazzo seed"
```

---

## Task 4: Boxy Zone rendering with percent-based positioning

**Files:**
- Modify: `frontend/src/components/Zone.tsx`
- Create: `frontend/tests/Zone.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/Zone.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Zone from '../src/components/Zone';

const zone = {
  id: 'dance',
  label: 'DANCE',
  x: 6.0,
  y: 8.0,
  width: 34.0,
  height: 36.0,
  color: '#ff6b9d',
  labelColor: '#ffffff',
  borderColor: '#8b1a4a',
};

describe('Zone', () => {
  it('renders as a boxy element with id-based aria-label', () => {
    render(<Zone zone={zone} />);
    const el = screen.getByLabelText('zone-dance');
    expect(el).toBeInTheDocument();
  });

  it('places the label text inside', () => {
    render(<Zone zone={zone} />);
    expect(screen.getByText('DANCE')).toBeInTheDocument();
  });

  it('uses percent-based positioning from zone coords', () => {
    render(<Zone zone={zone} />);
    const el = screen.getByLabelText('zone-dance') as HTMLElement;
    expect(el.style.left).toBe('6%');
    expect(el.style.top).toBe('8%');
    expect(el.style.width).toBe('34%');
    expect(el.style.height).toBe('36%');
  });

  it('uses solid fill color and a border in borderColor', () => {
    render(<Zone zone={zone} />);
    const el = screen.getByLabelText('zone-dance') as HTMLElement;
    expect(el.style.background).toContain('rgb(255, 107, 157)');
    expect(el.style.border).toContain('rgb(139, 26, 74)');
  });
});
```

- [ ] **Step 2: Run — verify it fails**

Run: `cd frontend && npm test -- Zone`
Expected: tests fail because the current Zone uses center-anchored absolute pixels and a radial-gradient.

- [ ] **Step 3: Replace `Zone.tsx`**

Replace `frontend/src/components/Zone.tsx` with:

```tsx
import type { Zone as ZoneType } from '../api/types';

type Props = { zone: ZoneType };

export default function Zone({ zone }: Props) {
  return (
    <div
      aria-label={`zone-${zone.id}`}
      style={{
        position: 'absolute',
        left: `${zone.x}%`,
        top: `${zone.y}%`,
        width: `${zone.width}%`,
        height: `${zone.height}%`,
        background: zone.color,
        border: `3px solid ${zone.borderColor}`,
        borderRadius: 6,
        pointerEvents: 'none',
        boxShadow: '0 2px 6px rgba(0,0,0,0.10)',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          color: zone.labelColor,
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: 1.5,
          textShadow: '0 1px 2px rgba(0,0,0,0.25)',
        }}
      >
        {zone.label}
      </div>
    </div>
  );
}
```

Note the props simplification: `Zone` no longer needs `worldWidth`/`worldHeight` because positioning is now percent-based relative to its parent container.

- [ ] **Step 4: Run — verify it passes**

Run: `cd frontend && npm test -- Zone`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Zone.tsx frontend/tests/Zone.test.tsx
git commit -m "feat(frontend): render zones as boxy filled rectangles with percent positioning"
```

---

## Task 5: Wall component

**Files:**
- Create: `frontend/src/components/Wall.tsx`

No dedicated test — Wall is exercised by Party test and PartyPreview test.

- [ ] **Step 1: Create `frontend/src/components/Wall.tsx`**

```tsx
import type { Wall as WallType } from '../api/types';

type Props = { wall: WallType };

export default function Wall({ wall }: Props) {
  return (
    <div
      data-testid="wall"
      style={{
        position: 'absolute',
        left: `${wall.x}%`,
        top: `${wall.y}%`,
        width: `${wall.width}%`,
        height: `${wall.height}%`,
        background: wall.color,
        pointerEvents: 'none',
      }}
    />
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Wall.tsx
git commit -m "feat(frontend): add Wall stub component"
```

---

## Task 6: Avatar percent-based positioning

**Files:**
- Modify: `frontend/src/components/Avatar.tsx`

Avatar's API now takes the world size so it can compute percent positions, since logical coords (x, y) are still in world units.

- [ ] **Step 1: Replace `Avatar.tsx`**

```tsx
type Props = {
  username: string;
  color: string;
  x: number;            // logical coord
  y: number;            // logical coord
  worldWidth: number;
  worldHeight: number;
};

export default function Avatar({ username, color, x, y, worldWidth, worldHeight }: Props) {
  const leftPct = (x / worldWidth) * 100;
  const topPct = (y / worldHeight) * 100;
  return (
    <div
      style={{
        position: 'absolute',
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none',
        transition: 'left 80ms linear, top 80ms linear',
      }}
    >
      <div
        style={{
          position: 'absolute',
          bottom: 28,
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 12,
          background: 'rgba(255,255,255,0.9)',
          padding: '1px 6px',
          borderRadius: 8,
          whiteSpace: 'nowrap',
          fontWeight: 600,
        }}
      >
        {username}
      </div>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: '50%',
          background: color,
          border: '2px solid white',
          boxShadow: '0 2px 6px rgba(0,0,0,0.25)',
        }}
      />
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: TS error in PartySpace.tsx because Avatar now requires `worldWidth`/`worldHeight`. **Leave the error** — Task 7 fixes the caller.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Avatar.tsx
git commit -m "feat(frontend): position Avatar via percent of world coords"
```

---

## Task 7: Responsive PartySpace with walls and clipPath

**Files:**
- Modify: `frontend/src/components/PartySpace.tsx`

- [ ] **Step 1: Replace `PartySpace.tsx`**

```tsx
import { useRef } from 'react';
import type { PartyConfig, User } from '../api/types';
import { useMovement } from '../hooks/useMovement';
import Avatar from './Avatar';
import MusicPill from './MusicPill';
import Wall from './Wall';
import Zone from './Zone';

const SPEED = 220; // logical units / sec

type Props = { party: PartyConfig; user: User };

export default function PartySpace({ party, user }: Props) {
  const { width, height } = party.worldSize;
  const { position, setTarget } = useMovement({
    worldWidth: width,
    worldHeight: height,
    speed: SPEED,
  });
  const floorRef = useRef<HTMLDivElement>(null);

  function onClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = floorRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    const logicalX = ((e.clientX - rect.left) / rect.width) * width;
    const logicalY = ((e.clientY - rect.top) / rect.height) * height;
    setTarget({ x: logicalX, y: logicalY });
  }

  return (
    <div
      style={{
        width: 'min(95vw, 1000px)',
        aspectRatio: `${width} / ${height}`,
        margin: '24px auto',
        position: 'relative',
      }}
    >
      <div
        ref={floorRef}
        onClick={onClick}
        style={{
          position: 'absolute',
          inset: 0,
          background: party.theme.floor,
          border: party.room.border,
          borderRadius: party.room.borderRadius ?? 0,
          clipPath: party.room.clipPath ?? 'none',
          overflow: 'hidden',
          boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        {party.zones.map((z) => (
          <Zone key={z.id} zone={z} />
        ))}
        {party.room.walls.map((w, i) => (
          <Wall key={i} wall={w} />
        ))}
        <Avatar
          username={user.username}
          color={user.color}
          x={position.x}
          y={position.y}
          worldWidth={width}
          worldHeight={height}
        />
        <MusicPill label={party.music.label} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc -b`
Expected: clean exit.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PartySpace.tsx
git commit -m "feat(frontend): responsive party room with walls and clipPath"
```

---

## Task 8: Update Party page test mock + add wall assertions

**Files:**
- Modify: `frontend/tests/Party.test.tsx`

- [ ] **Step 1: Replace the test file**

Replace `frontend/tests/Party.test.tsx` with:

```tsx
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Party from '../src/pages/Party';

const sessionResponse = {
  session_id: 'sid-1',
  username: 'Alice',
  color: '#ff6b9d',
};

const partyResponse = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  theme: { floor: '#f4ead5', accent: '#ff6b9d' },
  zones: [
    {
      id: 'dance',
      label: 'DANCE',
      x: 6,
      y: 8,
      width: 34,
      height: 36,
      color: '#ff6b9d',
      labelColor: '#ffffff',
      borderColor: '#8b1a4a',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: {
    clipPath: null,
    border: '6px solid #8b6f47',
    borderRadius: 12,
    walls: [
      { x: 50, y: 0, width: 0.75, height: 30, color: '#8b6f47' },
      { x: 75, y: 40, width: 25, height: 1.2, color: '#8b6f47' },
    ],
  },
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('Party', () => {
  beforeEach(() => {
    localStorage.setItem('session_id', 'sid-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes('/api/session/')) return jsonResponse(sessionResponse);
      if (u.endsWith('/api/parties/cream-terrazzo')) return jsonResponse(partyResponse);
      if (u.endsWith('/api/parties/unknown')) return jsonResponse({ detail: 'nope' }, 404);
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('renders party space, zones, avatar, walls, and music placeholder', async () => {
    render(
      <MemoryRouter initialEntries={['/party/cream-terrazzo']}>
        <Routes>
          <Route path="/party/:slug" element={<Party />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByLabelText('zone-dance')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText(/music coming soon/i)).toBeInTheDocument();
    // Both wall stubs from the mock render.
    expect(screen.getAllByTestId('wall')).toHaveLength(2);
  });

  it('redirects to /lobby when slug is unknown', async () => {
    render(
      <MemoryRouter initialEntries={['/party/unknown']}>
        <Routes>
          <Route path="/party/:slug" element={<Party />} />
          <Route path="/lobby" element={<div>Lobby page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/lobby page/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — verify it passes**

Run: `cd frontend && npm test -- Party`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/Party.test.tsx
git commit -m "test(frontend): Party test mock includes room and asserts walls"
```

---

## Task 9: PartyPreview component (TDD)

**Files:**
- Create: `frontend/src/components/PartyPreview.tsx`
- Create: `frontend/tests/PartyPreview.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/PartyPreview.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PartyPreview from '../src/components/PartyPreview';

const party = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  theme: { floor: '#f4ead5', accent: '#ff6b9d' },
  zones: [
    {
      id: 'dance',
      label: 'DANCE',
      x: 6,
      y: 8,
      width: 34,
      height: 36,
      color: '#ff6b9d',
      labelColor: '#ffffff',
      borderColor: '#8b1a4a',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: {
    clipPath: null,
    border: '6px solid #8b6f47',
    borderRadius: 12,
    walls: [
      { x: 50, y: 0, width: 0.75, height: 30, color: '#8b6f47' },
    ],
  },
};

describe('PartyPreview', () => {
  it('renders zones and walls from the party config', () => {
    render(<PartyPreview party={party} />);
    expect(screen.getByLabelText('zone-dance')).toBeInTheDocument();
    expect(screen.getAllByTestId('wall')).toHaveLength(1);
  });

  it('does not render avatar or music pill', () => {
    render(<PartyPreview party={party} />);
    expect(screen.queryByText(/music coming soon/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — verify it fails**

Run: `cd frontend && npm test -- PartyPreview`
Expected: module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/components/PartyPreview.tsx`:

```tsx
import type { PartyConfig } from '../api/types';
import Wall from './Wall';
import Zone from './Zone';

type Props = { party: PartyConfig };

export default function PartyPreview({ party }: Props) {
  const { width, height } = party.worldSize;
  return (
    <div
      style={{
        width: '100%',
        aspectRatio: `${width} / ${height}`,
        position: 'relative',
      }}
      aria-label={`preview-${party.slug}`}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: party.theme.floor,
          border: party.room.border,
          borderRadius: party.room.borderRadius ?? 0,
          clipPath: party.room.clipPath ?? 'none',
          overflow: 'hidden',
          pointerEvents: 'none',
        }}
      >
        {party.zones.map((z) => (
          <Zone key={z.id} zone={z} />
        ))}
        {party.room.walls.map((w, i) => (
          <Wall key={i} wall={w} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run — verify it passes**

Run: `cd frontend && npm test -- PartyPreview`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PartyPreview.tsx frontend/tests/PartyPreview.test.tsx
git commit -m "feat(frontend): add PartyPreview component"
```

---

## Task 10: Lobby uses PartyPreview + responsive layout

**Files:**
- Modify: `frontend/src/pages/Lobby.tsx`
- Modify: `frontend/tests/Lobby.test.tsx`

- [ ] **Step 1: Update the test**

Replace `frontend/tests/Lobby.test.tsx` with:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Lobby from '../src/pages/Lobby';

const sessionResponse = {
  session_id: 'sid-1',
  username: 'Alice',
  color: '#ff6b9d',
};

const partiesResponse = {
  parties: [
    {
      slug: 'cream-terrazzo',
      name: 'Cream Terrazzo Lounge',
      description: 'A bright, friendly room.',
      theme: { floor: '#f4ead5', accent: '#ff6b9d' },
      zones: [
        {
          id: 'dance',
          label: 'DANCE',
          x: 6,
          y: 8,
          width: 34,
          height: 36,
          color: '#ff6b9d',
          labelColor: '#ffffff',
          borderColor: '#8b1a4a',
        },
      ],
      music: { url: null, label: 'Music coming soon' },
      worldSize: { width: 800, height: 500 },
      room: {
        clipPath: null,
        border: '6px solid #8b6f47',
        borderRadius: 12,
        walls: [{ x: 50, y: 0, width: 0.75, height: 30, color: '#8b6f47' }],
      },
    },
  ],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('Lobby', () => {
  beforeEach(() => {
    localStorage.setItem('session_id', 'sid-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes('/api/session/')) return jsonResponse(sessionResponse);
      if (u.endsWith('/api/parties')) return jsonResponse(partiesResponse);
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('renders a card per party with a mini preview', async () => {
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <Routes>
          <Route path="/lobby" element={<Lobby />} />
          <Route path="/party/:slug" element={<div>Party page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Cream Terrazzo Lounge/i)).toBeInTheDocument();
    expect(screen.getByLabelText('preview-cream-terrazzo')).toBeInTheDocument();
  });

  it('navigates to /party/:slug when a card is clicked', async () => {
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <Routes>
          <Route path="/lobby" element={<Lobby />} />
          <Route path="/party/:slug" element={<div>Party page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    const card = await screen.findByRole('button', { name: /cream terrazzo lounge/i });
    await userEvent.click(card);
    expect(await screen.findByText(/Party page/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run — verify it fails**

Run: `cd frontend && npm test -- Lobby`
Expected: FAIL — the `preview-cream-terrazzo` label doesn't render yet.

- [ ] **Step 3: Update Lobby.tsx**

Replace `frontend/src/pages/Lobby.tsx` with:

```tsx
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';
import type { PartiesListResponse, PartyConfig } from '../api/types';
import PartyPreview from '../components/PartyPreview';
import { useSession } from '../hooks/useSession';

export default function Lobby() {
  const session = useSession();
  const navigate = useNavigate();
  const [parties, setParties] = useState<PartyConfig[] | null>(null);

  useEffect(() => {
    if (session.status !== 'authed') return;
    apiGet<PartiesListResponse>('/api/parties')
      .then((res) => setParties(res.parties))
      .catch(() => setParties([]));
  }, [session.status]);

  if (session.status !== 'authed') return null;

  return (
    <main
      style={{
        maxWidth: 'min(1100px, 92vw)',
        margin: 'clamp(24px, 6vh, 40px) auto',
        padding: 'clamp(16px, 4vw, 24px)',
      }}
    >
      <h1 style={{ fontSize: 'clamp(22px, 5vw, 32px)', margin: 0 }}>
        Pick a party, {session.user.username}
      </h1>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))',
          gap: 16,
          marginTop: 16,
        }}
      >
        {parties === null && <p>Loading parties…</p>}
        {parties?.map((p) => (
          <button
            key={p.slug}
            type="button"
            onClick={() => navigate(`/party/${p.slug}`)}
            style={{
              textAlign: 'left',
              padding: 12,
              border: `2px solid ${p.theme.accent}`,
              borderRadius: 12,
              background: '#fff',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            <PartyPreview party={p} />
            <div>
              <strong>{p.name}</strong>
              <p style={{ margin: '4px 0 0', color: '#555' }}>{p.description}</p>
            </div>
          </button>
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Run — verify it passes**

Run: `cd frontend && npm test -- Lobby`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Lobby.tsx frontend/tests/Lobby.test.tsx
git commit -m "feat(frontend): Lobby uses PartyPreview and responsive layout"
```

---

## Task 11: Responsive SignIn and Party page

**Files:**
- Modify: `frontend/src/pages/SignIn.tsx`
- Modify: `frontend/src/pages/Party.tsx`

No test changes — existing tests still pass because semantics are unchanged.

- [ ] **Step 1: Tweak `SignIn.tsx`**

Find the `<main>` style block and replace its style prop with:

```tsx
style={{
  maxWidth: 'min(420px, 92vw)',
  margin: 'clamp(24px, 8vh, 64px) auto',
  padding: 'clamp(16px, 4vw, 24px)',
}}
```

And the `<h1>` should become:

```tsx
<h1 style={{ fontSize: 'clamp(20px, 5vw, 28px)', margin: 0 }}>
  Welcome to ai_agent_party
</h1>
```

(All other markup unchanged.)

- [ ] **Step 2: Tweak `Party.tsx`**

Replace the `<header>` block with:

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
  <button type="button" onClick={() => navigate('/lobby')}>
    Leave party
  </button>
</header>
```

(Other markup unchanged.)

- [ ] **Step 3: Run full suite**

Run: `cd frontend && npm test`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SignIn.tsx frontend/src/pages/Party.tsx
git commit -m "feat(frontend): responsive SignIn and Party page styles"
```

---

## Task 12: Full verification

**Files:** none

- [ ] **Step 1: All backend tests**

Run: `cd backend && source .venv/bin/activate && pytest -v`
Expected: all pass.

- [ ] **Step 2: All frontend tests**

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 3: Frontend production build**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Browser smoke test**

Boot backend (`uvicorn app.main:app --reload --port 8000`) and frontend (`npm run dev`). In the browser:
- Lobby card now shows a mini room with floor color, walls, and zones.
- Resize the window — party room scales smoothly with viewport, stays 16:10.
- Phone viewport (375x667 via dev tools): Lobby shows one card per row, party room is shrunk but fully visible.
- Zones are solid filled boxes with thick borders, not see-through ovals.
- Two wall stubs visible in the Cream Terrazzo room.
- WASD and click-to-move still work; avatar stays inside floor bounds.
