# Phase 5 — Speech Bubbles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface existing broadcast `ChatEvent`s as ephemeral speech bubbles above avatars and add a chat input pinned to the party view. No persistence, no DMs, no scrollback.

**Architecture:** Frontend-only on top of the existing WS realtime infra. `useRealtimeParty` gains a `bubbles` state (map of `participantId → { text, expiresAt }`) populated from `chat` events; a `<ChatBubble>` component renders one bubble per active entry, anchored to the current participant position; a `<ChatInput>` calls the existing `chatInParty()` API. Bubbles expire after 5 s via a 250 ms tick in the hook; CSS fades the last 500 ms. Backend gains only one regression test asserting the WS chat frame shape the frontend reads.

**Tech Stack:** React 18 + TypeScript + vitest + React Testing Library (frontend); FastAPI + pytest + httpx (backend); shared regex/length constants are duplicated to TS rather than fetched at runtime.

**Spec:** [`docs/superpowers/specs/2026-05-13-phase5-speech-bubbles-design.md`](../specs/2026-05-13-phase5-speech-bubbles-design.md)

**Prerequisite:** This plan assumes the WebSocket realtime infra from `feat/session-takeover` (or any subsequent merge of it) is on the base branch. `realtime.py`, `useRealtimeParty.ts`, and `PartySpace` participants wiring must exist before Task 2 starts. Do not begin execution until that prerequisite is on main.

---

## File Map

**Backend (1 regression test, no new modules)**
- Test: `backend/tests/test_realtime_chat_frame.py` (new)

**Frontend (new files)**
- `frontend/src/api/validation.ts` — mirrors backend chat regex + max-length constants
- `frontend/src/components/ChatBubble.tsx` — single bubble, positioned above an avatar
- `frontend/src/components/ChatInput.tsx` — bottom-pinned input that POSTs chat
- Tests: `frontend/tests/validation.test.ts`, `frontend/tests/ChatBubble.test.tsx`, `frontend/tests/ChatInput.test.tsx`

**Frontend (modified)**
- `frontend/src/hooks/useRealtimeParty.ts` — add `bubbles` to state + expiry tick + `chat` event branch + `leave` prunes bubble
- `frontend/tests/useRealtimeParty.test.ts` — add chat-event + leave-prune + expiry tests (extend the existing file, reuse its `MockWebSocket` stub)
- `frontend/src/components/PartySpace.tsx` — render `<ChatBubble>` per active entry; mount `<ChatInput>`
- `frontend/tests/PartySpace.multi.test.tsx` — extend with bubble & input tests (reuse the existing `party` fixture)
- `frontend/src/pages/Party.tsx` — pass slug + principal + status to `<PartySpace>` (small edit)

---

## Task 1: Backend regression test — `ChatEvent` WS frame shape

The frontend will read `participant_id`, `text`, `at`, and `seq` from the WS frame. Lock that contract with a backend test.

**Files:**
- Create: `backend/tests/test_realtime_chat_frame.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_realtime_chat_frame.py
"""Regression: WS chat frame must include participant_id, text, at, seq.

These are the fields the frontend (useRealtimeParty + ChatBubble) reads.
Keep this test in sync with frontend expectations.
"""
from app.events import ChatEvent
from app.realtime import _serialise_event


def test_chat_event_ws_frame_has_required_fields() -> None:
    event = ChatEvent(seq=42, participant_id="abc", text="hi", at=1700000000.0)

    frame = _serialise_event(event)

    assert frame["type"] == "event"
    assert frame["cursor"] == 42
    payload = frame["event"]
    assert payload["type"] == "chat"
    assert payload["participant_id"] == "abc"
    assert payload["text"] == "hi"
    assert payload["at"] == 1700000000.0
    assert payload["seq"] == 42
```

- [ ] **Step 2: Run the test to confirm it passes (the contract should already hold)**

Run: `cd backend && pytest tests/test_realtime_chat_frame.py -v`

Expected: **PASS** (1 test). The existing `_serialise_event` already does `event.model_dump()` and `ChatEvent` already has all four fields. If it fails, the contract has drifted — fix `_serialise_event` so the test passes before continuing.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_realtime_chat_frame.py
git commit -m "test(realtime): lock WS chat frame shape for frontend contract"
```

---

## Task 2: Frontend shared chat validation constants

Mirror the backend's `CHAT_TEXT_REGEX` + `CHAT_MAX_LEN`. Plain module — no React.

**Files:**
- Create: `frontend/src/api/validation.ts`
- Test: `frontend/tests/validation.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/tests/validation.test.ts
import { describe, it, expect } from 'vitest';
import {
  CHAT_MAX_LEN,
  CHAT_TEXT_REGEX,
  validateChatText,
} from '../../src/api/validation';

describe('chat validation', () => {
  it('exports the same max length as the backend', () => {
    expect(CHAT_MAX_LEN).toBe(280);
  });

  it('accepts allowed characters', () => {
    expect(CHAT_TEXT_REGEX.test('hello, world!')).toBe(true);
  });

  it('rejects disallowed characters', () => {
    expect(CHAT_TEXT_REGEX.test('hi 🙂')).toBe(false);
    expect(CHAT_TEXT_REGEX.test('a@b')).toBe(false);
  });

  it('validateChatText returns trimmed text on success', () => {
    expect(validateChatText('  hi  ')).toEqual({ ok: true, text: 'hi' });
  });

  it('validateChatText returns reason on empty input', () => {
    expect(validateChatText('   ')).toEqual({
      ok: false,
      reason: 'empty',
    });
  });

  it('validateChatText returns reason on over-length input', () => {
    const long = 'a'.repeat(CHAT_MAX_LEN + 1);
    expect(validateChatText(long)).toEqual({
      ok: false,
      reason: 'too_long',
    });
  });

  it('validateChatText returns reason on disallowed chars', () => {
    expect(validateChatText('hi 🙂')).toEqual({
      ok: false,
      reason: 'invalid_chars',
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/validation.test.ts`

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the module**

```ts
// frontend/src/api/validation.ts
// Mirrors backend/app/validation.py — keep in sync.
export const CHAT_MAX_LEN = 280;
export const CHAT_TEXT_REGEX = /^[A-Za-z0-9 .,!?'\-]+$/;

export type ChatValidationResult =
  | { ok: true; text: string }
  | { ok: false; reason: 'empty' | 'too_long' | 'invalid_chars' };

export function validateChatText(raw: string): ChatValidationResult {
  const trimmed = raw.trim();
  if (trimmed.length === 0) return { ok: false, reason: 'empty' };
  if (trimmed.length > CHAT_MAX_LEN) return { ok: false, reason: 'too_long' };
  if (!CHAT_TEXT_REGEX.test(trimmed)) {
    return { ok: false, reason: 'invalid_chars' };
  }
  return { ok: true, text: trimmed };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/validation.test.ts`

Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/validation.ts frontend/tests/validation.test.ts
git commit -m "feat(frontend): shared chat validation mirroring backend"
```

---

## Task 3: Extend `useRealtimeParty` with bubbles state

Add `bubbles: Record<string, Bubble>` where `Bubble = { text: string; expiresAt: number }`. Populate on `chat`, replace on subsequent `chat` from same speaker, prune on `leave`, expire via a 250 ms interval.

**Files:**
- Modify: `frontend/src/hooks/useRealtimeParty.ts`
- Modify: `frontend/tests/useRealtimeParty.test.ts` (add tests, reuse `MockWebSocket` stub already defined at the top of the file)

- [ ] **Step 1: Add the failing tests**

Append the following block to the **end** of `frontend/tests/useRealtimeParty.test.ts` (keep existing imports + `MockWebSocket` class + `beforeEach/afterEach` global setup intact). The file already imports `act, renderHook, beforeEach, afterEach, describe, expect, it, vi` and globally stubs `WebSocket` to `MockWebSocket` — reuse all of that.

Also add `BUBBLE_LIFETIME_MS` to the existing import from `useRealtimeParty`:

```ts
// at the top of the test file, update the existing import:
import { useRealtimeParty, BUBBLE_LIFETIME_MS } from '../src/hooks/useRealtimeParty';
```

```ts
// inside frontend/tests/useRealtimeParty.test.ts — append after the existing
// `describe('useRealtimeParty', ...)` block.

function chatFrame(participant_id: string, text: string, seq: number) {
  return {
    type: 'event',
    cursor: seq,
    event: {
      type: 'chat',
      seq,
      participant_id,
      text,
      at: 1700000000 + seq,
    },
  };
}

describe('useRealtimeParty — chat bubbles', () => {
  it('starts with no bubbles', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.bubbles).toEqual({});
  });

  it('adds a bubble on chat event', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() => ws.receive(chatFrame('them', 'hi', 5)));
    expect(result.current.bubbles['them']?.text).toBe('hi');
    expect(result.current.bubbles['them']?.expiresAt).toBeGreaterThan(Date.now());
  });

  it('replaces a previous bubble from the same participant', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.receive(chatFrame('them', 'first', 1));
      ws.receive(chatFrame('them', 'second', 2));
    });
    expect(result.current.bubbles['them']?.text).toBe('second');
  });

  it('prunes a bubble when its owner leaves', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() => {
      ws.receive(chatFrame('them', 'hi', 1));
      ws.receive({
        type: 'event',
        cursor: 2,
        event: { type: 'leave', seq: 2, participant_id: 'them', at: 1700000001 },
      });
    });
    expect(result.current.bubbles['them']).toBeUndefined();
  });

  it('sets expiresAt to roughly BUBBLE_LIFETIME_MS in the future', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    const before = Date.now();
    act(() => ws.receive(chatFrame('them', 'hi', 1)));
    const after = Date.now();
    const bubble = result.current.bubbles['them'];
    expect(bubble).toBeDefined();
    // Allow generous slack for slow test runs.
    expect(bubble!.expiresAt).toBeGreaterThanOrEqual(before + BUBBLE_LIFETIME_MS - 50);
    expect(bubble!.expiresAt).toBeLessThanOrEqual(after + BUBBLE_LIFETIME_MS + 50);
  });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd frontend && npx vitest run tests/useRealtimeParty.test.ts`

Expected: 5 new failures — `result.current.bubbles` is undefined.

- [ ] **Step 3: Update `useRealtimeParty.ts`**

Replace the hook's body so it exposes `bubbles` and handles `chat` + expiry + leave-prune. Full updated file:

```ts
// frontend/src/hooks/useRealtimeParty.ts
import { useEffect, useRef, useState } from 'react';
import type { Participant } from '../api/types';
import type { Principal } from '../api/party';

type Options = {
  slug: string;
  principal: Principal;
  onEvicted?: () => void;
};

type Status = 'connecting' | 'open' | 'closed';

export type Bubble = { text: string; expiresAt: number };
export type Bubbles = Record<string, Bubble>;

export const BUBBLE_LIFETIME_MS = 5000;
const BUBBLE_TICK_MS = 250;

function wsUrlFor(slug: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/parties/${slug}/ws`;
}

export function useRealtimeParty({ slug, principal, onEvicted }: Options) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [bubbles, setBubbles] = useState<Bubbles>({});
  const [status, setStatus] = useState<Status>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const evictedRef = useRef(false);

  // Expiry tick: prunes bubbles whose expiresAt has passed.
  useEffect(() => {
    const id = setInterval(() => {
      setBubbles((prev) => {
        const now = Date.now();
        let changed = false;
        const next: Bubbles = {};
        for (const [k, b] of Object.entries(prev)) {
          if (b.expiresAt > now) next[k] = b;
          else changed = true;
        }
        return changed ? next : prev;
      });
    }, BUBBLE_TICK_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!slug || !principal.id) return;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled) return;
      setStatus('connecting');
      const ws = new WebSocket(wsUrlFor(slug));
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', principal }));
        backoffRef.current = 1000;
        setStatus('open');
      };

      ws.onmessage = (e: MessageEvent) => {
        let frame: unknown;
        try {
          frame = JSON.parse(typeof e.data === 'string' ? e.data : '');
        } catch {
          return;
        }
        if (!frame || typeof frame !== 'object') return;
        const f = frame as { type?: string };
        if (f.type === 'evicted') {
          evictedRef.current = true;
          onEvicted?.();
          ws.close();
          return;
        }
        if (f.type === 'snapshot') {
          const s = frame as { participants: Participant[] };
          setParticipants(s.participants);
        } else if (f.type === 'event') {
          const ev = (frame as { event: { type: string } }).event;
          if (ev.type === 'join') {
            const p = (ev as unknown as { participant: Participant }).participant;
            setParticipants((prev) =>
              prev.some((q) => q.id === p.id) ? prev : [...prev, p],
            );
          } else if (ev.type === 'leave') {
            const id = (ev as unknown as { participant_id: string }).participant_id;
            setParticipants((prev) => prev.filter((q) => q.id !== id));
            setBubbles((prev) => {
              if (!(id in prev)) return prev;
              const next = { ...prev };
              delete next[id];
              return next;
            });
          } else if (ev.type === 'move') {
            const m = ev as unknown as { participant_id: string; x: number; y: number };
            if (m.participant_id === principal.id) return;
            setParticipants((prev) =>
              prev.map((q) =>
                q.id === m.participant_id ? { ...q, x: m.x, y: m.y } : q,
              ),
            );
          } else if (ev.type === 'chat') {
            const c = ev as unknown as { participant_id: string; text: string };
            setBubbles((prev) => ({
              ...prev,
              [c.participant_id]: {
                text: c.text,
                expiresAt: Date.now() + BUBBLE_LIFETIME_MS,
              },
            }));
          }
        }
      };

      ws.onclose = () => {
        setStatus('closed');
        if (cancelled || evictedRef.current) return;
        const delay = Math.min(backoffRef.current, 8000);
        backoffRef.current = Math.min(backoffRef.current * 2, 8000);
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onerror = () => {};
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer != null) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [slug, principal.id, principal.kind]);

  return { participants, status, bubbles };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/useRealtimeParty.test.ts`

Expected: all tests pass (existing tests still green; new chat-bubble tests green).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useRealtimeParty.ts frontend/tests/useRealtimeParty.test.ts
git commit -m "feat(realtime): expose bubbles state from useRealtimeParty"
```

---

## Task 4: `ChatBubble` component

Pure presentational. Receives world-coords `(x, y)` of the speaker, world dimensions, and `text`. Rendered absolutely-positioned inside the floor div (parent provides the world rect), translated above the avatar, with a CSS fade-out class applied when `expiresAt - now < 500`.

The component does **not** own a timer. The hook prunes it from state when expired; the bubble simply renders or doesn't.

**Files:**
- Create: `frontend/src/components/ChatBubble.tsx`
- Test: `frontend/tests/ChatBubble.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/ChatBubble.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ChatBubble from '../src/components/ChatBubble';

describe('ChatBubble', () => {
  it('renders the message text', () => {
    render(
      <ChatBubble
        text="hello there"
        x={50}
        y={50}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 5000}
      />,
    );
    expect(screen.getByText('hello there')).toBeInTheDocument();
  });

  it('positions itself as a percentage of world dimensions', () => {
    render(
      <ChatBubble
        text="x"
        x={25}
        y={75}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 5000}
      />,
    );
    const el = screen.getByText('x').parentElement!;
    expect(el.style.left).toBe('25%');
    expect(el.style.top).toBe('75%');
  });

  it('applies fading class when within 500ms of expiry', () => {
    render(
      <ChatBubble
        text="x"
        x={0}
        y={0}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 200}
      />,
    );
    const el = screen.getByText('x').parentElement!;
    expect(el.getAttribute('data-fading')).toBe('true');
  });

  it('does not mark fading when far from expiry', () => {
    render(
      <ChatBubble
        text="x"
        x={0}
        y={0}
        worldWidth={100}
        worldHeight={100}
        expiresAt={Date.now() + 4000}
      />,
    );
    const el = screen.getByText('x').parentElement!;
    expect(el.getAttribute('data-fading')).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/ChatBubble.test.tsx`

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/ChatBubble.tsx
type Props = {
  text: string;
  x: number;
  y: number;
  worldWidth: number;
  worldHeight: number;
  expiresAt: number;
};

const FADE_WINDOW_MS = 500;

export default function ChatBubble({
  text,
  x,
  y,
  worldWidth,
  worldHeight,
  expiresAt,
}: Props) {
  const leftPct = (x / worldWidth) * 100;
  const topPct = (y / worldHeight) * 100;
  const fading = expiresAt - Date.now() <= FADE_WINDOW_MS;
  return (
    <div
      data-fading={fading ? 'true' : undefined}
      style={{
        position: 'absolute',
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: 'translate(-50%, calc(-100% - 28px))',
        pointerEvents: 'none',
        background: 'rgba(255,255,255,0.95)',
        color: '#2a2a2a',
        border: '1px solid #c9b58a',
        borderRadius: 10,
        padding: '3px 8px',
        fontSize: 12,
        boxShadow: '0 2px 4px rgba(0,0,0,0.12)',
        maxWidth: 200,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        opacity: fading ? 0 : 1,
        transition: 'opacity 500ms ease-out',
        zIndex: 5,
      }}
    >
      {text}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/ChatBubble.test.tsx`

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatBubble.tsx frontend/tests/ChatBubble.test.tsx
git commit -m "feat(chat): ChatBubble component for ephemeral speech"
```

---

## Task 5: `ChatInput` component

Single-line input pinned to the bottom of the party view. Enter to send; calls existing `chatInParty(slug, principal, text)`. Disabled with title text when `disabled` prop is true (parent passes `status !== 'open'`). Shows inline validation message under the input on client-side failure. Clears on successful send.

**Files:**
- Create: `frontend/src/components/ChatInput.tsx`
- Test: `frontend/tests/ChatInput.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/ChatInput.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ChatInput from '../src/components/ChatInput';
import * as partyApi from '../src/api/party';

describe('ChatInput', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders an input', () => {
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('calls chatInParty on Enter and clears the input', async () => {
    const spy = vi
      .spyOn(partyApi, 'chatInParty')
      .mockResolvedValue({ cursor: 1 });
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'hi there' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(spy).toHaveBeenCalledWith('cream-terrazzo', { kind: 'human', id: 'me' }, 'hi there');
    // Wait a microtask for the awaited then-clear.
    await Promise.resolve();
    expect(input.value).toBe('');
  });

  it('refuses to send invalid characters and shows a message', () => {
    const spy = vi.spyOn(partyApi, 'chatInParty');
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'hi 🙂' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText(/disallowed/i)).toBeInTheDocument();
  });

  it('refuses to send empty input', () => {
    const spy = vi.spyOn(partyApi, 'chatInParty');
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={false}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(spy).not.toHaveBeenCalled();
  });

  it('disables the input when status is closed', () => {
    render(
      <ChatInput
        slug="cream-terrazzo"
        principal={{ kind: 'human', id: 'me' }}
        disabled={true}
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run tests/ChatInput.test.tsx`

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/ChatInput.tsx
import { useState } from 'react';
import { chatInParty, type Principal } from '../api/party';
import { CHAT_MAX_LEN, validateChatText } from '../api/validation';

type Props = {
  slug: string;
  principal: Principal;
  disabled: boolean;
};

const REASON_MESSAGES: Record<string, string> = {
  empty: '',
  too_long: `Message too long (max ${CHAT_MAX_LEN} characters)`,
  invalid_chars: 'Message contains disallowed characters',
};

export default function ChatInput({ slug, principal, disabled }: Props) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string>('');
  const [sending, setSending] = useState(false);

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key !== 'Enter') return;
    if (sending || disabled) return;
    const result = validateChatText(value);
    if (!result.ok) {
      setError(REASON_MESSAGES[result.reason] ?? '');
      return;
    }
    setError('');
    setSending(true);
    chatInParty(slug, principal, result.text)
      .then(() => {
        setValue('');
      })
      .catch(() => {
        setError('Failed to send');
      })
      .finally(() => {
        setSending(false);
      });
  }

  return (
    <div
      style={{
        position: 'absolute',
        left: 12,
        right: 12,
        bottom: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        zIndex: 10,
      }}
    >
      <input
        type="text"
        value={value}
        disabled={disabled || sending}
        title={disabled ? 'Reconnecting…' : undefined}
        placeholder={disabled ? 'Reconnecting…' : 'Say something…'}
        maxLength={CHAT_MAX_LEN}
        onChange={(e) => {
          setValue(e.target.value);
          if (error) setError('');
        }}
        onKeyDown={onKeyDown}
        style={{
          width: '100%',
          padding: '8px 12px',
          fontSize: 14,
          borderRadius: 999,
          border: '1px solid #c9b58a',
          background: disabled ? '#eee' : '#fff',
          outline: 'none',
          boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
        }}
      />
      {error && (
        <div
          role="alert"
          style={{
            fontSize: 12,
            color: '#b03030',
            background: 'rgba(255,255,255,0.9)',
            padding: '2px 8px',
            borderRadius: 6,
            alignSelf: 'flex-start',
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run tests/ChatInput.test.tsx`

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatInput.tsx frontend/tests/ChatInput.test.tsx
git commit -m "feat(chat): ChatInput component with client-side validation"
```

---

## Task 6: Wire bubbles + input into `PartySpace`

`PartySpace` now accepts `bubbles` and renders one `<ChatBubble>` per entry at the speaker's current `(x, y)` (looked up from `participants`). It also mounts `<ChatInput>` inside the floor container.

Because `PartySpace` doesn't currently know `slug` / `principal` / WS `status`, add those props. The Party page (`pages/Party.tsx`) already has all three.

**Files:**
- Modify: `frontend/src/components/PartySpace.tsx`
- Modify: `frontend/tests/PartySpace.multi.test.tsx`
- Modify: `frontend/src/pages/Party.tsx`

- [ ] **Step 1: Add failing tests for PartySpace**

Append to the **end** of `frontend/tests/PartySpace.multi.test.tsx`, keeping the existing tests + the `party`, `selfUser`, `participants` fixtures defined at the top of the file. Reuse those fixtures rather than redeclaring them.

```tsx
// inside frontend/tests/PartySpace.multi.test.tsx — append below the existing describe.

describe('PartySpace — chat bubbles & input', () => {
  it('renders a bubble for each entry in bubbles, anchored to participant position', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={participants}
        bubbles={{ 'sid-2': { text: 'hello', expiresAt: Date.now() + 5000 } }}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="open"
      />,
    );
    expect(screen.getByText('hello')).toBeInTheDocument();
  });

  it('does not render a bubble for a participant no longer in the list', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={[]}
        bubbles={{ ghost: { text: 'lost', expiresAt: Date.now() + 5000 } }}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="open"
      />,
    );
    expect(screen.queryByText('lost')).not.toBeInTheDocument();
  });

  it('mounts a chat input', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={[]}
        bubbles={{}}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="open"
      />,
    );
    expect(screen.getByPlaceholderText(/say something/i)).toBeInTheDocument();
  });

  it('disables the input when status is not open', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={[]}
        bubbles={{}}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="connecting"
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run tests/PartySpace.multi.test.tsx`

Expected: 4 new failures (existing tests still pass).

- [ ] **Step 3: Update `PartySpace.tsx`**

Extend `Props` and the body. Patch is below — apply the additions while preserving everything else in the file.

New props on `Props`:

```tsx
type Props = {
  party: PartyConfig;
  user: User;
  participants?: Participant[];
  onMove?: (x: number, y: number) => void;
  bubbles?: Record<string, { text: string; expiresAt: number }>;
  slug: string;
  principal: { kind: 'human' | 'agent'; id: string };
  status: 'connecting' | 'open' | 'closed';
};
```

After the existing `<MusicPill .../>` line, before the closing `</div>`, add bubbles + input:

```tsx
{Object.entries(bubbles ?? {}).map(([participantId, bubble]) => {
  const speaker = renderList.find((p) => p.id === participantId);
  if (!speaker) return null;
  return (
    <ChatBubble
      key={participantId}
      text={bubble.text}
      x={speaker.x}
      y={speaker.y}
      worldWidth={width}
      worldHeight={height}
      expiresAt={bubble.expiresAt}
    />
  );
})}
<ChatInput slug={slug} principal={principal} disabled={status !== 'open'} />
```

At the top of the file add:

```tsx
import ChatBubble from './ChatBubble';
import ChatInput from './ChatInput';
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run tests/PartySpace.multi.test.tsx`

Expected: PASS (all tests, old and new).

- [ ] **Step 5: Update `pages/Party.tsx` to pass the new props**

Locate the line that reads `const { participants } = useRealtimeParty(...)` and replace with:

```tsx
const { participants, bubbles, status } = useRealtimeParty(
  ready && principal
    ? { slug: party!.slug, principal, onEvicted: handleTakeover }
    : { slug: '', principal: { kind: 'human', id: '' } },
);
```

Then update the `<PartySpace ... />` render to pass the new props:

```tsx
<PartySpace
  party={party}
  user={session.user}
  participants={participants}
  onMove={onMove}
  bubbles={bubbles}
  slug={party.slug}
  principal={principal!}
  status={status}
/>
```

(Keep all other props/wiring identical.)

- [ ] **Step 6: Run the full frontend test suite**

Run: `cd frontend && npx vitest run`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/PartySpace.tsx frontend/src/pages/Party.tsx frontend/tests/PartySpace.multi.test.tsx
git commit -m "feat(party): render speech bubbles and mount chat input"
```

---

## Task 7: Manual smoke + full suite

Verify end-to-end in a browser, then run the entire backend + frontend suites once more.

- [ ] **Step 1: Start backend**

```bash
cd backend
source .venv/bin/activate  # create with `python3.11 -m venv .venv && pip install -r requirements.txt` if missing
uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Start frontend in a second terminal**

```bash
cd frontend
npm run dev
```

- [ ] **Step 3: Open two browser windows**

1. http://localhost:5173 — sign in as `Mason` (any color).
2. Another window / incognito — sign in as `Aria`.
3. Both join the Cream Terrazzo Lounge.
4. From Mason's window, type `hello` in the chat input + Enter.
5. Verify: a bubble saying "hello" appears above Mason's avatar in both windows and fades after ~5 s.
6. From Aria's window, type `hi mason` + Enter. Verify bubble above Aria's avatar in both windows.
7. Move Mason while a bubble is alive — bubble follows the avatar.
8. Type a string with disallowed chars (`hi 🙂`) — input shows inline error, no bubble appears, no POST sent.

- [ ] **Step 4: Backend full suite**

Run: `cd backend && pytest`

Expected: all tests pass.

- [ ] **Step 5: Frontend full suite**

Run: `cd frontend && npx vitest run`

Expected: all tests pass.

- [ ] **Step 6: Final commit — none expected**

If steps 1-5 produced any incidental edits (e.g., test fixture cleanups), commit them now:

```bash
git status
# if dirty:
git add -A
git commit -m "chore(phase5): minor cleanup after manual smoke"
```

---

## Out of Scope (Phase 6)

- SQLite persistence of broadcast or DM messages.
- DM threads, inbox WS, scrollback UI, unread badges.
- Bubble collision avoidance / stacking when multiple speakers overlap.
- Rate-limiting, abuse handling, attachments, emoji, rich text.
- `CLAUDE.md` "What's Implemented" update — defer to a single docs sweep after Phase 6 lands so it captures both phases together.
