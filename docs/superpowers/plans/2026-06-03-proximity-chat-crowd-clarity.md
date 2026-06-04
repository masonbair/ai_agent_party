# Proximity Chat & Crowd-Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chat visible only to participants within proximity (with a contentless "someone's talking" indicator for far-away speakers), color chat-bubble borders by speaker, stop avatars from stacking, deepen the chat cooldown, and prevent chat bubbles from overlapping.

**Architecture:** The backend already has proximity machinery (`proximity.py`, `world.visible_to`). The human browser connects to `PartyWorldHub` (`/ws`), which currently broadcasts everything. We make that hub filter `chat` per-subscriber — full bubble in range, redacted "ambient" frame out of range — while positions/presence stay global. Avatar separation is enforced server-side in `world.move` (covers agents) and mirrored client-side in `useMovement` (human prediction). Bubble coloring and anti-overlap layout are presentation-only.

**Tech Stack:** FastAPI + pytest (backend), Vite + React + TypeScript + vitest/RTL (frontend).

**Working directory:** This plan executes in the worktree `.worktrees/proximity-chat` on branch `feat/proximity-chat`. All paths below are relative to that worktree root.

**Spec:** `docs/superpowers/specs/2026-06-03-proximity-chat-crowd-clarity-design.md`

---

## Scope decision (read first)

Per the spec, proximity filtering in the human hub is applied to **`chat` events only**. `reaction`/`gesture`/module events keep their current broadcast behavior to avoid regressing existing tests; they are brief visual flourishes and already proximity-scoped on the agent `/observe` path. `move`, `join`, `leave`, and all `room_wide=True` events remain global so everyone always sees where avatars are.

## File structure

**Backend**
- `backend/app/rate_limit.py` (modify) — chat cooldown values.
- `backend/app/collision.py` (modify) — add `separate()` helper + `MIN_AVATAR_SEPARATION`.
- `backend/app/world.py` (modify) — apply separation in `move()` and `_move_internal()`.
- `backend/app/realtime.py` (modify) — per-subscriber chat filtering + ambient frame; track `participant_id` per socket.

**Frontend**
- `frontend/src/hooks/useMovement.ts` (modify) — client-side avatar separation.
- `frontend/src/hooks/useRealtimeParty.ts` (modify) — ambient bubble handling; `Bubble.ambient`.
- `frontend/src/components/ChatBubble.tsx` (modify) — colored border + ambient puff variant + `offsetY`.
- `frontend/src/components/PartySpace.tsx` (modify) — pass speaker color, anti-overlap bubble offsets, feed other-avatar positions to `useMovement`.

**Tests** (create/modify)
- `backend/tests/test_chat_cooldown.py` (modify or add case)
- `backend/tests/test_collision.py` (add cases)
- `backend/tests/test_world_collision.py` (add separation case)
- `backend/tests/test_realtime_proximity_chat.py` (create)
- `frontend/tests/useMovement.test.ts` (add case)
- `frontend/tests/ChatBubble.test.tsx` (add cases)
- `frontend/tests/useRealtimeParty.test.ts` (add case)
- `frontend/tests/bubbleLayout.test.ts` (create)

---

## Task 1: Deepen the chat cooldown

**Files:**
- Modify: `backend/app/rate_limit.py:30-33`
- Test: `backend/tests/test_rate_limit.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_rate_limit.py`:

```python
def test_proximity_chat_allows_one_then_blocks_for_about_four_seconds():
    from app.rate_limit import RateLimiter, CHAT_BUCKETS

    t = {"now": 1000.0}
    rl = RateLimiter(configs=CHAT_BUCKETS, now=lambda: t["now"])

    ok, retry = rl.try_consume("cream-terrazzo", "actor-1", "proximity")
    assert ok is True and retry == 0

    # Immediate second message is blocked (no bursting).
    ok2, retry2 = rl.try_consume("cream-terrazzo", "actor-1", "proximity")
    assert ok2 is False
    assert 3500 <= retry2 <= 4000  # ~4s until next token

    # After 4s a token is available again.
    t["now"] += 4.0
    ok3, _ = rl.try_consume("cream-terrazzo", "actor-1", "proximity")
    assert ok3 is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_rate_limit.py::test_proximity_chat_allows_one_then_blocks_for_about_four_seconds -v`
Expected: FAIL — current config is `burst=2`, so the second consume returns `ok=True`.

- [ ] **Step 3: Update the cooldown config**

In `backend/app/rate_limit.py`, replace the `CHAT_BUCKETS` block (lines 30-33):

```python
# Deepened cooldown (2026-06-03): no bursting; ~1 message / 4s for proximity
# chat, slower for room-wide. Keeps crowded rooms readable.
CHAT_BUCKETS: dict[str, BucketConfig] = {
    "proximity": BucketConfig(burst=1, refill_seconds=4.0),
    "room": BucketConfig(burst=1, refill_seconds=8.0),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_rate_limit.py tests/test_chat_cooldown.py -v`
Expected: PASS. If an existing case in `test_chat_cooldown.py` asserted the old burst=2 behavior, update its expectation to the new burst=1 (one message, then a ~4s wait).

- [ ] **Step 5: Commit**

```bash
git add backend/app/rate_limit.py backend/tests/test_rate_limit.py backend/tests/test_chat_cooldown.py
git commit -m "feat(chat): deepen proximity chat cooldown to ~1 msg / 4s"
```

---

## Task 2: Avatar separation helper (`collision.separate`)

**Files:**
- Modify: `backend/app/collision.py`
- Test: `backend/tests/test_collision.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_collision.py`:

```python
from app.collision import separate, MIN_AVATAR_SEPARATION


def test_separate_pushes_apart_overlapping_point():
    # Two avatars 10 units apart (< MIN_AVATAR_SEPARATION) push to >= min.
    moved = separate((100.0, 100.0), [(110.0, 100.0)], MIN_AVATAR_SEPARATION)
    dist = ((moved[0] - 110.0) ** 2 + (moved[1] - 100.0) ** 2) ** 0.5
    assert dist >= MIN_AVATAR_SEPARATION - 1e-6
    # Pushed away from the other avatar (to the left).
    assert moved[0] < 100.0


def test_separate_leaves_distant_point_untouched():
    moved = separate((100.0, 100.0), [(500.0, 500.0)], MIN_AVATAR_SEPARATION)
    assert moved == (100.0, 100.0)


def test_separate_handles_exact_overlap_deterministically():
    moved = separate((100.0, 100.0), [(100.0, 100.0)], MIN_AVATAR_SEPARATION)
    # Nudged by exactly one separation along +x; never NaN.
    assert moved == (100.0 + MIN_AVATAR_SEPARATION, 100.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_collision.py -k separate -v`
Expected: FAIL with `ImportError: cannot import name 'separate'`.

- [ ] **Step 3: Implement the helper**

Add to `backend/app/collision.py` (after the `AVATAR_RADIUS` constant, and `import math` at the top):

```python
import math

# Minimum center-to-center distance between two avatars (touching circles).
MIN_AVATAR_SEPARATION = 2 * AVATAR_RADIUS


def separate(
    point: tuple[float, float],
    others: list[tuple[float, float]],
    min_dist: float,
) -> tuple[float, float]:
    """Push ``point`` out of any avatar in ``others`` it overlaps.

    Single, deterministic push-out step (not an iterative physics solve):
    for each overlapping other, shift ``point`` along the line away from it
    so the pair end up ``min_dist`` apart. Exact overlap (dist == 0) is
    nudged a fixed amount along +x so the result is never NaN.
    """
    x, y = point
    for ox, oy in others:
        dx, dy = x - ox, y - oy
        dist = math.hypot(dx, dy)
        if dist >= min_dist:
            continue
        if dist == 0.0:
            x += min_dist
            continue
        push = (min_dist - dist) / dist
        x += dx * push
        y += dy * push
    return (x, y)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_collision.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/collision.py backend/tests/test_collision.py
git commit -m "feat(collision): add avatar separation helper"
```

---

## Task 3: Enforce separation server-side in `world.move`

**Files:**
- Modify: `backend/app/world.py:399-428` (`move`) and `backend/app/world.py:453-475` (`_move_internal`)
- Test: `backend/tests/test_world_collision.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_world_collision.py`:

```python
import math

from app.collision import MIN_AVATAR_SEPARATION
from app.events import Participant
from app.parties_data import CREAM_TERRAZZO
from app.world import PartyWorld


def _p(pid: str, x: float, y: float) -> Participant:
    return Participant(
        id=pid, kind="human", username=pid, color="#ff6b9d",
        x=x, y=y, joined_at=1715533200.0,
    )


def test_move_separates_overlapping_avatars():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 300.0, 300.0))
    world.join(_p("b", 600.0, 300.0))
    # b tries to walk onto a's exact spot.
    world.move("b", 300.0, 300.0)
    a = world.participants["a"]
    b = world.participants["b"]
    dist = math.hypot(a.x - b.x, a.y - b.y)
    assert dist >= MIN_AVATAR_SEPARATION - 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_world_collision.py::test_move_separates_overlapping_avatars -v`
Expected: FAIL — `b` ends up at `(300, 300)`, distance 0.

- [ ] **Step 3: Apply separation in `move`**

In `backend/app/world.py`, add this import near the other `collision` import at the top of the file (find the existing `from app.collision import ... slide`):

```python
from app.collision import MIN_AVATAR_SEPARATION, separate
```

Then in `move` (currently lines 403-408), after the `slide(...)` call that computes `new_x, new_y`, insert a separation step before deriving facing:

```python
        new_x, new_y = slide(
            (current.x, current.y),
            (float(x), float(y)),
            self._wall_rects,
            self._party.worldSize,
        )
        others = [
            (p.x, p.y)
            for pid, p in self.participants.items()
            if pid != participant_id
        ]
        sep_x, sep_y = separate((new_x, new_y), others, MIN_AVATAR_SEPARATION)
        # Re-resolve walls/bounds in case separation pushed into a wall.
        new_x, new_y = slide(
            (new_x, new_y), (sep_x, sep_y), self._wall_rects, self._party.worldSize
        )
```

Apply the **same** `others`/`separate`/`slide` re-resolve block in `_move_internal` (lines 457-462), right after its `slide(...)` call, so follower auto-moves also separate.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_world_collision.py tests/test_collision.py tests/test_follow_auto_move.py tests/test_move_facing.py -v`
Expected: PASS. (The follow + facing suites exercise `move`/`_move_internal`; they must stay green.)

- [ ] **Step 5: Run the full backend suite to catch position-sensitive regressions**

Run: `cd backend && python -m pytest -q`
Expected: PASS. If a test placed two participants at the same coordinates and asserted an exact post-move position, update it to expect the separated position (distance ≥ `MIN_AVATAR_SEPARATION`).

- [ ] **Step 6: Commit**

```bash
git add backend/app/world.py backend/tests/test_world_collision.py
git commit -m "feat(world): separate overlapping avatars on move"
```

---

## Task 4: Per-subscriber proximity chat + ambient frame in the hub

**Files:**
- Modify: `backend/app/realtime.py`
- Test: `backend/tests/test_realtime_proximity_chat.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_realtime_proximity_chat.py`:

```python
import asyncio

import pytest

from app.events import Participant
from app.parties_data import CREAM_TERRAZZO
from app.realtime import PartyWorldHub
from app.world import PartyWorld


def _p(pid: str, x: float, y: float) -> Participant:
    return Participant(
        id=pid, kind="human", username=pid, color="#ff6b9d",
        x=x, y=y, joined_at=1715533200.0,
    )


class FakeSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True


def _chat_frames(sock: FakeSocket) -> list[dict]:
    return [
        f["event"]
        for f in sock.sent
        if f.get("type") == "event" and f["event"].get("type") == "chat"
    ]


@pytest.mark.asyncio
async def test_in_range_subscriber_gets_full_chat():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 300.0, 300.0))
    world.join(_p("b", 320.0, 300.0))  # within PROXIMITY_RADIUS of a
    hub = PartyWorldHub(world)
    sock_b = FakeSocket()
    hub.subscribe(sock_b, principal_key="human:b", participant_id="b")

    world.chat("a", "hello neighbor")
    await hub.drain()

    frames = _chat_frames(sock_b)
    assert len(frames) == 1
    assert frames[0]["text"] == "hello neighbor"
    assert frames[0].get("ambient") in (False, None)


@pytest.mark.asyncio
async def test_out_of_range_subscriber_gets_ambient_only():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 100.0, 100.0))
    world.join(_p("c", 900.0, 700.0))  # far from a
    hub = PartyWorldHub(world)
    sock_c = FakeSocket()
    hub.subscribe(sock_c, principal_key="human:c", participant_id="c")

    world.chat("a", "secret nearby talk")
    await hub.drain()

    frames = _chat_frames(sock_c)
    assert len(frames) == 1
    assert frames[0]["ambient"] is True
    assert "text" not in frames[0] or frames[0]["text"] == ""
    assert frames[0]["actor_id"] == "a"  # so the client can place the puff


@pytest.mark.asyncio
async def test_room_wide_chat_reaches_everyone_with_text():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 100.0, 100.0))
    world.join(_p("c", 900.0, 700.0))
    hub = PartyWorldHub(world)
    sock_c = FakeSocket()
    hub.subscribe(sock_c, principal_key="human:c", participant_id="c")

    world.chat("a", "EVERYONE LISTEN", scope="room")
    await hub.drain()

    frames = _chat_frames(sock_c)
    assert len(frames) == 1
    assert frames[0]["text"] == "EVERYONE LISTEN"


@pytest.mark.asyncio
async def test_move_is_global_regardless_of_distance():
    world = PartyWorld(CREAM_TERRAZZO)
    world.join(_p("a", 100.0, 100.0))
    world.join(_p("c", 900.0, 700.0))
    hub = PartyWorldHub(world)
    sock_c = FakeSocket()
    hub.subscribe(sock_c, principal_key="human:c", participant_id="c")

    world.move("a", 120.0, 120.0)
    await hub.drain()

    moves = [
        f["event"] for f in sock_c.sent
        if f.get("type") == "event" and f["event"].get("type") == "move"
    ]
    assert len(moves) >= 1  # far-away movement still delivered
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_realtime_proximity_chat.py -v`
Expected: FAIL — today the out-of-range socket receives the full chat text (no ambient redaction).

- [ ] **Step 3: Add a per-socket participant map + filtering to the hub**

In `backend/app/realtime.py`:

Add the chat event import near the top (with the existing `from app.events import Event`):

```python
from app.events import ChatEvent, Event
```

Add an ambient serializer next to `_serialise_event`:

```python
def _serialise_ambient_chat(event: ChatEvent) -> dict:
    """A contentless chat frame for out-of-range observers: enough to render a
    'someone's talking over there' puff, with the message text omitted."""
    return {
        "type": "event",
        "event": {
            "type": "chat",
            "seq": event.seq,
            "actor_id": event.actor_id,
            "actor_username": event.actor_username,
            "actor_kind": event.actor_kind,
            "actor_color": event.actor_color,
            "at": event.at,
            "ambient": True,
        },
        "cursor": event.seq,
    }
```

In `PartyWorldHub.__init__`, add a socket→participant map:

```python
        self._participant_by_sock: dict[SocketLike, str] = {}
```

In `subscribe`, record it (after `self.subscribers.add(sock)`):

```python
        self._participant_by_sock[sock] = participant_id
```

In `unsubscribe` and in the drop path of `_send_or_drop` and in `_evict`, remove the socket from the map wherever the socket is discarded. Add `self._participant_by_sock.pop(sock, None)` alongside each existing `self.subscribers.discard(sock)` call.

Replace `_on_event` so chat is filtered per subscriber while everything else broadcasts unchanged:

```python
    def _on_event(self, event: Event) -> None:
        snapshot = list(self.subscribers)
        if not snapshot:
            return
        full = _serialise_event(event)
        # Only chat is proximity-scoped here; positions/presence/room-wide
        # events broadcast unchanged.
        if not isinstance(event, ChatEvent) or getattr(event, "room_wide", False):
            for sock in snapshot:
                self._dispatch(self._send_or_drop(sock, full))
            return
        ambient = _serialise_ambient_chat(event)
        for sock in snapshot:
            pid = self._participant_by_sock.get(sock)
            in_range = pid is not None and self.world.visible_to(pid, event)
            self._dispatch(self._send_or_drop(sock, full if in_range else ambient))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_realtime_proximity_chat.py tests/test_realtime.py tests/test_realtime_route.py tests/test_realtime_chat_frame.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/realtime.py backend/tests/test_realtime_proximity_chat.py
git commit -m "feat(realtime): proximity-scope chat; ambient frame for far speakers"
```

---

## Task 5: Frontend — ambient bubbles in `useRealtimeParty`

**Files:**
- Modify: `frontend/src/hooks/useRealtimeParty.ts:27-31` (types/consts) and `:276-285` (chat handler)
- Test: `frontend/tests/useRealtimeParty.test.ts`

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/useRealtimeParty.test.ts` (inside the existing `describe('useRealtimeParty', ...)`):

```python
  it('records an ambient bubble (no text) for ambient chat frames', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'event',
        cursor: 7,
        event: { type: 'chat', actor_id: 'sid-2', ambient: true, seq: 7 },
      }),
    );
    expect(result.current.bubbles['sid-2']).toBeDefined();
    expect(result.current.bubbles['sid-2'].ambient).toBe(true);
    expect(result.current.bubbles['sid-2'].text).toBe('');
  });
```

> Note: the test file is TypeScript — the block above is `.ts`; ignore the fence label.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/useRealtimeParty.test.ts -t ambient`
Expected: FAIL — `bubbles['sid-2']` is `undefined` (ambient flag not handled).

- [ ] **Step 3: Extend the Bubble type and chat handler**

In `frontend/src/hooks/useRealtimeParty.ts`, update the Bubble type and add an ambient lifetime (lines 27-31):

```typescript
export type Bubble = { text: string; expiresAt: number; ambient?: boolean };
export type Bubbles = Record<string, Bubble>;

export const BUBBLE_LIFETIME_MS = 5000;
export const AMBIENT_BUBBLE_LIFETIME_MS = 2000;
const BUBBLE_TICK_MS = 250;
```

Replace the `ev.type === 'chat'` branch (lines 276-285):

```typescript
          } else if (ev.type === 'chat') {
            const c = ev as unknown as {
              actor_id: string;
              text?: string;
              ambient?: boolean;
            };
            const ambient = c.ambient === true;
            setBubbles((prev) => ({
              ...prev,
              [c.actor_id]: {
                text: ambient ? '' : c.text ?? '',
                ambient,
                expiresAt:
                  Date.now() +
                  (ambient ? AMBIENT_BUBBLE_LIFETIME_MS : BUBBLE_LIFETIME_MS),
              },
            }));
          }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/useRealtimeParty.test.ts`
Expected: PASS (existing chat test still green — full chat frames keep their text and `ambient` is `false`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useRealtimeParty.ts frontend/tests/useRealtimeParty.test.ts
git commit -m "feat(frontend): handle ambient chat frames as contentless bubbles"
```

---

## Task 6: `ChatBubble` — colored border, ambient puff, vertical offset

**Files:**
- Modify: `frontend/src/components/ChatBubble.tsx`
- Test: `frontend/tests/ChatBubble.test.tsx`

- [ ] **Step 1: Write the failing tests**

Add to `frontend/tests/ChatBubble.test.tsx` (inside the `describe`):

```tsx
  it('uses the speaker color for the border', () => {
    render(
      <ChatBubble
        text="hi"
        color="#4dd0e1"
        x={50}
        y={50}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 5000}
      />,
    );
    const el = screen.getByText('hi').parentElement!;
    // jsdom normalizes hex to rgb in border shorthand; assert the color is present.
    expect(el.style.border).toContain('1px solid');
    expect(el.style.borderColor || el.style.border).toMatch(/77, 208, 225|#4dd0e1/);
  });

  it('renders an ambient puff with no message text', () => {
    render(
      <ChatBubble
        text=""
        ambient
        color="#4dd0e1"
        x={50}
        y={50}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 2000}
      />,
    );
    expect(screen.getByText('···')).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run tests/ChatBubble.test.tsx`
Expected: FAIL — `color`/`ambient` props don't exist; border is hardcoded `#c9b58a`; no `···`.

- [ ] **Step 3: Update `ChatBubble`**

Replace `frontend/src/components/ChatBubble.tsx` with:

```tsx
// frontend/src/components/ChatBubble.tsx
type Props = {
  text: string;
  x: number;
  y: number;
  worldWidth: number;
  worldHeight: number;
  expiresAt: number;
  color?: string;
  ambient?: boolean;
  /** Extra upward shift (px) applied by the anti-overlap layout. */
  offsetY?: number;
};

const FADE_WINDOW_MS = 500;
const DEFAULT_BORDER = '#c9b58a';

export default function ChatBubble({
  text,
  x,
  y,
  worldWidth,
  worldHeight,
  expiresAt,
  color,
  ambient = false,
  offsetY = 0,
}: Props) {
  const leftPct = (x / worldWidth) * 100;
  const topPct = (y / worldHeight) * 100;
  const fading = expiresAt - Date.now() <= FADE_WINDOW_MS;
  const translateX = leftPct < 30 ? '0%' : leftPct > 70 ? '-100%' : '-50%';
  const borderColor = color ?? DEFAULT_BORDER;
  const liftPx = 28 + offsetY;

  if (ambient) {
    // Contentless "someone's talking over there" puff: small, faded, no text.
    return (
      <div
        data-ambient="true"
        data-fading={fading ? 'true' : undefined}
        style={{
          position: 'absolute',
          left: `${leftPct}%`,
          top: `${topPct}%`,
          transform: `translate(-50%, calc(-100% - ${liftPx}px))`,
          pointerEvents: 'none',
          background: 'rgba(255,255,255,0.65)',
          color: '#888',
          border: `1px dashed ${borderColor}`,
          borderRadius: 10,
          padding: '1px 6px',
          fontSize: 11,
          lineHeight: 1,
          opacity: fading ? 0 : 0.7,
          transition: 'left 150ms linear, top 150ms linear, opacity 400ms ease-out',
          zIndex: 4,
        }}
      >
        <span>···</span>
      </div>
    );
  }

  return (
    <div
      data-fading={fading ? 'true' : undefined}
      style={{
        position: 'absolute',
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: `translate(${translateX}, calc(-100% - ${liftPx}px))`,
        pointerEvents: 'none',
        background: 'rgba(255,255,255,0.95)',
        color: '#2a2a2a',
        border: `1px solid ${borderColor}`,
        borderRadius: 10,
        padding: '3px 8px',
        fontSize: 12,
        boxShadow: '0 2px 4px rgba(0,0,0,0.12)',
        width: 'max-content',
        maxWidth: 260,
        whiteSpace: 'normal',
        wordBreak: 'break-word',
        display: '-webkit-box',
        WebkitBoxOrient: 'vertical',
        WebkitLineClamp: 2,
        overflow: 'hidden',
        textAlign: 'center',
        lineHeight: 1.3,
        opacity: fading ? 0 : 1,
        transition: 'left 150ms linear, top 150ms linear, opacity 500ms ease-out',
        zIndex: 5,
      }}
    >
      <span>{text}</span>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/ChatBubble.test.tsx`
Expected: PASS (existing tests still green — `color`/`ambient`/`offsetY` are optional).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatBubble.tsx frontend/tests/ChatBubble.test.tsx
git commit -m "feat(frontend): color chat-bubble borders by speaker + ambient puff"
```

---

## Task 7: Anti-overlap bubble layout helper

**Files:**
- Create: `frontend/src/components/bubbleLayout.ts`
- Test: `frontend/tests/bubbleLayout.test.ts` (create)

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/bubbleLayout.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { computeBubbleOffsets } from '../src/components/bubbleLayout';

describe('computeBubbleOffsets', () => {
  it('gives non-overlapping bubbles a zero offset', () => {
    const offsets = computeBubbleOffsets([
      { id: 'a', x: 100, y: 100 },
      { id: 'b', x: 600, y: 100 },
    ]);
    expect(offsets.a).toBe(0);
    expect(offsets.b).toBe(0);
  });

  it('stacks bubbles whose anchors are close together', () => {
    const offsets = computeBubbleOffsets([
      { id: 'a', x: 100, y: 100 },
      { id: 'b', x: 120, y: 110 }, // close in both axes
    ]);
    // One stays at base, the other is lifted by at least one level.
    const lifted = [offsets.a, offsets.b].filter((o) => o > 0);
    expect(lifted.length).toBe(1);
    expect(Math.max(offsets.a, offsets.b)).toBeGreaterThanOrEqual(34);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/bubbleLayout.test.ts`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the helper**

Create `frontend/src/components/bubbleLayout.ts`:

```typescript
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/bubbleLayout.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/bubbleLayout.ts frontend/tests/bubbleLayout.test.ts
git commit -m "feat(frontend): bubble anti-overlap layout helper"
```

---

## Task 8: Wire color + ambient + offsets through `PartySpace`

**Files:**
- Modify: `frontend/src/components/PartySpace.tsx:286-300` (bubble render) and `:54` (Props bubbles type)
- Test: `frontend/tests/PartySpace.multi.test.tsx`

- [ ] **Step 1: Write the failing test**

Add a case to `frontend/tests/PartySpace.multi.test.tsx`. First inspect the file's existing render helper/imports and reuse them. Add:

```tsx
  it('passes speaker color to the chat bubble border', () => {
    // Reuse this file's existing party/user fixtures + render helper.
    const { container } = renderPartySpace({
      participants: [
        { id: 'sid-1', kind: 'human', username: 'me', color: '#ff6b9d', x: 100, y: 100 },
        { id: 'sid-2', kind: 'human', username: 'bob', color: '#4dd0e1', x: 300, y: 300 },
      ],
      bubbles: { 'sid-2': { text: 'hello', expiresAt: Date.now() + 5000 } },
    });
    const bubble = screen.getByText('hello').parentElement!;
    expect(bubble.style.border).toMatch(/77, 208, 225|#4dd0e1/);
    expect(container).toBeTruthy();
  });
```

> If `PartySpace.multi.test.tsx` has no reusable `renderPartySpace` helper, mirror the existing test's inline render (same props it already passes) and add `bubbles` + the two participants.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/PartySpace.multi.test.tsx -t "speaker color"`
Expected: FAIL — bubble border is still the default `#c9b58a`.

- [ ] **Step 3: Update the bubble render block + Props type**

In `frontend/src/components/PartySpace.tsx`, update the `bubbles` prop type (line 54) to carry the ambient flag:

```tsx
  bubbles?: Record<string, { text: string; expiresAt: number; ambient?: boolean }>;
```

Add the layout import near the other component imports (around line 17):

```tsx
import { computeBubbleOffsets } from './bubbleLayout';
```

Replace the bubble render block (lines 286-300):

```tsx
        {(() => {
          const entries = Object.entries(bubbles ?? {}).flatMap(
            ([participantId, bubble]) => {
              const speaker = renderList.find((p) => p.id === participantId);
              return speaker ? [{ participantId, bubble, speaker }] : [];
            },
          );
          const offsets = computeBubbleOffsets(
            entries.map((e) => ({ id: e.participantId, x: e.speaker.x, y: e.speaker.y })),
          );
          return entries.map(({ participantId, bubble, speaker }) => (
            <ChatBubble
              key={participantId}
              text={bubble.text}
              ambient={bubble.ambient}
              color={speaker.color}
              offsetY={offsets[participantId] ?? 0}
              x={speaker.x}
              y={speaker.y}
              worldWidth={width}
              worldHeight={height}
              expiresAt={bubble.expiresAt}
            />
          ));
        })()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/PartySpace.multi.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PartySpace.tsx frontend/tests/PartySpace.multi.test.tsx
git commit -m "feat(frontend): color bubbles by speaker + anti-overlap offsets in PartySpace"
```

---

## Task 9: Client-side avatar separation in `useMovement`

**Files:**
- Modify: `frontend/src/hooks/useMovement.ts`
- Test: `frontend/tests/useMovement.test.ts`

- [ ] **Step 1: Write the failing test**

Add to `frontend/tests/useMovement.test.ts` (reuse the file's existing `renderHook` + raf-driving pattern; inspect it first). The key assertion is that the exported pure helper separates points:

```typescript
import { separatePoint, MIN_AVATAR_SEPARATION } from '../src/hooks/useMovement';

describe('separatePoint', () => {
  it('pushes a point out of an overlapping neighbor', () => {
    const moved = separatePoint({ x: 100, y: 100 }, [{ x: 110, y: 100 }]);
    const dist = Math.hypot(moved.x - 110, moved.y - 100);
    expect(dist).toBeGreaterThanOrEqual(MIN_AVATAR_SEPARATION - 1e-6);
    expect(moved.x).toBeLessThan(100);
  });

  it('leaves a distant point unchanged', () => {
    const moved = separatePoint({ x: 100, y: 100 }, [{ x: 500, y: 500 }]);
    expect(moved).toEqual({ x: 100, y: 100 });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/useMovement.test.ts -t separatePoint`
Expected: FAIL — `separatePoint` / `MIN_AVATAR_SEPARATION` not exported.

- [ ] **Step 3: Add the helper, option, and loop integration**

In `frontend/src/hooks/useMovement.ts`:

Add the constant + exported helper near the other constants (after line 40):

```typescript
export const MIN_AVATAR_SEPARATION = 2 * AVATAR_RADIUS;

// Mirror of backend `collision.separate`: one deterministic push-out step so
// the local avatar's predicted position matches the server's.
export function separatePoint(point: Point, others: Point[]): Point {
  let { x, y } = point;
  for (const o of others) {
    const dx = x - o.x;
    const dy = y - o.y;
    const dist = Math.hypot(dx, dy);
    if (dist >= MIN_AVATAR_SEPARATION) continue;
    if (dist === 0) {
      x += MIN_AVATAR_SEPARATION;
      continue;
    }
    const push = (MIN_AVATAR_SEPARATION - dist) / dist;
    x += dx * push;
    y += dy * push;
  }
  return { x, y };
}
```

Add an `others` getter to `Options` (after `paused?` in the type, around line 25):

```typescript
  /**
   * Returns the current positions of OTHER avatars (excluding self), in world
   * units. Used to softly separate the local avatar so bodies don't stack.
   */
  getOthers?: () => Point[];
```

Wire a ref for it next to `onMoveRef` (after line 190):

```typescript
  const getOthersRef = useRef(opts.getOthers);
  getOthersRef.current = opts.getOthers;
```

In the animation loop, apply separation after wall resolution and before the final clamp. Replace the clamp block (lines 366-369):

```typescript
      const others = getOthersRef.current?.() ?? [];
      const separated =
        others.length > 0 ? separatePoint({ x: nx, y: ny }, others) : { x: nx, y: ny };

      const clamped = {
        x: clamp(separated.x, 0, worldWidth),
        y: clamp(separated.y, 0, worldHeight),
      };
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/useMovement.test.ts`
Expected: PASS (existing movement tests still green — `getOthers` is optional and defaults to no separation).

- [ ] **Step 5: Feed other-avatar positions from `PartySpace`**

In `frontend/src/components/PartySpace.tsx`, pass `getOthers` into the `useMovement` call (the `useMovement({...})` at lines 80-88). Add:

```tsx
    getOthers: () =>
      (participants ?? [])
        .filter((p) => p.id !== user.session_id)
        .map((p) => ({ x: p.x, y: p.y })),
```

- [ ] **Step 6: Run the relevant frontend suites**

Run: `cd frontend && npx vitest run tests/useMovement.test.ts tests/PartySpace.multi.test.tsx tests/Party.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/hooks/useMovement.ts frontend/src/components/PartySpace.tsx frontend/tests/useMovement.test.ts
git commit -m "feat(frontend): client-side avatar separation in useMovement"
```

---

## Task 10: Full verification + docs

**Files:**
- Modify: `CLAUDE.md` (add a changelog entry under the dated sections)

- [ ] **Step 1: Run the entire backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS.

- [ ] **Step 2: Run the entire frontend suite + typecheck**

Run: `cd frontend && npx vitest run && npx tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 3: Manual smoke (optional but recommended)**

Start backend (`cd backend && uvicorn app.main:app --reload`) and frontend (`cd frontend && npm run dev`). Open two browser sessions with different colors. Verify: (a) chat from a far avatar shows only a "···" puff; walking close reveals the text; (b) each speaker's bubble border matches their avatar color; (c) two avatars can't fully overlap; (d) two nearby speakers' bubbles stack instead of overlapping; (e) sending two messages quickly shows the "slow down" notice.

- [ ] **Step 4: Add a CLAUDE.md changelog entry**

Append under the existing dated sections in `CLAUDE.md`:

```markdown
### Proximity chat & crowd clarity (2026-06-03)
- Human realtime hub (`PartyWorldHub`) now proximity-scopes `chat`: in-range
  subscribers get the full bubble; out-of-range get a contentless `ambient`
  frame (no text) so the client can show a "···" puff. Positions/presence
  (`move`/`join`/`leave`) and `room_wide` events stay global. Reactions/gestures
  unchanged.
- Chat-bubble borders take the speaker's avatar color; ambient puffs use a
  dashed faint variant.
- Avatars softly separate (min `2 * AVATAR_RADIUS`): enforced server-side in
  `world.move`/`_move_internal` (covers agents) via `collision.separate`, and
  mirrored client-side in `useMovement.separatePoint`.
- Overlapping chat bubbles stack upward via `bubbleLayout.computeBubbleOffsets`.
- Deeper chat cooldown: proximity `burst=1, refill=4s` (room `8s`).
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: changelog for proximity chat + crowd clarity"
```

---

## Self-review notes (coverage map)

- Spec goal 1 (proximity chat, humans + agents) → Task 4 (humans via hub; agents already scoped on `/observe`).
- Spec goal 2 (ambient indicator, humans-only) → Tasks 4 (backend ambient frame), 5 (hook), 6 (puff render).
- Spec goal 3 (colored borders) → Tasks 6, 8.
- Spec goal 4 (soft separation, humans + agents) → Tasks 2, 3 (server/agents), 9 (client/humans).
- Spec goal 5 (anti-overlap bubbles) → Tasks 7, 8.
- Spec goal 6 (deeper cooldown) → Task 1.
- Type consistency: `MIN_AVATAR_SEPARATION` (backend `collision.py` + frontend `useMovement.ts`), `separate`/`separatePoint`, `Bubble.ambient`, `ambient`/`color`/`offsetY` props, `computeBubbleOffsets` — all defined where first used and consumed with matching names.
```
