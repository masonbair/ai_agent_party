import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRealtimeParty, BUBBLE_LIFETIME_MS } from '../src/hooks/useRealtimeParty';
import type { Principal } from '../src/api/party';

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.readyState = MockWebSocket.OPEN;
      this.onopen?.(new Event('open'));
    });
  }

  send(payload: string) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }

  receive(obj: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(obj) }));
  }
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket);
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const selfPrincipal: Principal = { kind: 'human', id: 'sid-1' };

describe('useRealtimeParty', () => {
  it('opens a WS to the party slug and sends auth as the first frame', async () => {
    renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain('/api/parties/cream-terrazzo/ws');
    expect(JSON.parse(ws.sent[0])).toEqual({
      type: 'auth',
      principal: selfPrincipal,
    });
  });

  it('populates participants from a snapshot', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'snapshot',
        room: {},
        participants: [
          { id: 'sid-1', kind: 'human', username: 'alice', color: '#ff6b9d', x: 100, y: 100 },
          { id: 'sid-2', kind: 'human', username: 'bob', color: '#4dd0e1', x: 200, y: 200 },
        ],
        cursor: 5,
      }),
    );
    expect(result.current.participants.map((p) => p.id).sort()).toEqual(['sid-1', 'sid-2']);
  });

  it('applies a join event', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() => ws.receive({ type: 'snapshot', room: {}, participants: [], cursor: 0 }));
    act(() =>
      ws.receive({
        type: 'event',
        event: {
          seq: 1,
          type: 'join',
          participant: {
            id: 'sid-2',
            kind: 'human',
            username: 'bob',
            color: '#4dd0e1',
            x: 200,
            y: 200,
          },
        },
        cursor: 1,
      }),
    );
    expect(result.current.participants).toHaveLength(1);
    expect(result.current.participants[0].username).toBe('bob');
  });

  it('updates position from a move event for other participants', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'snapshot',
        room: {},
        participants: [
          { id: 'sid-2', kind: 'human', username: 'bob', color: '#4dd0e1', x: 200, y: 200 },
        ],
        cursor: 0,
      }),
    );
    act(() =>
      ws.receive({
        type: 'event',
        event: { seq: 1, type: 'move', participant_id: 'sid-2', x: 300, y: 250 },
        cursor: 1,
      }),
    );
    const bob = result.current.participants.find((p) => p.id === 'sid-2')!;
    expect(bob.x).toBe(300);
    expect(bob.y).toBe(250);
  });

  it('ignores move events for self', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'snapshot',
        room: {},
        participants: [
          { id: 'sid-1', kind: 'human', username: 'alice', color: '#ff6b9d', x: 100, y: 100 },
        ],
        cursor: 0,
      }),
    );
    act(() =>
      ws.receive({
        type: 'event',
        event: { seq: 1, type: 'move', participant_id: 'sid-1', x: 999, y: 999 },
        cursor: 1,
      }),
    );
    const me = result.current.participants.find((p) => p.id === 'sid-1')!;
    expect(me.x).toBe(100); // unchanged
  });

  it('removes a participant on leave', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 'cream-terrazzo', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'snapshot',
        room: {},
        participants: [
          { id: 'sid-2', kind: 'human', username: 'bob', color: '#4dd0e1', x: 200, y: 200 },
        ],
        cursor: 0,
      }),
    );
    act(() =>
      ws.receive({
        type: 'event',
        event: { seq: 1, type: 'leave', participant_id: 'sid-2' },
        cursor: 1,
      }),
    );
    expect(result.current.participants).toHaveLength(0);
  });

  it('invokes onEvicted, closes, and suppresses reconnect on an evicted frame', async () => {
    const onEvicted = vi.fn();
    renderHook(() =>
      useRealtimeParty({
        slug: 'cream-terrazzo',
        principal: selfPrincipal,
        onEvicted,
      }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() => ws.receive({ type: 'snapshot', room: {}, participants: [], cursor: 0 }));

    act(() => ws.receive({ type: 'evicted', reason: 'takeover' }));

    expect(onEvicted).toHaveBeenCalledTimes(1);
    expect(ws.readyState).toBe(MockWebSocket.CLOSED);

    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });
});

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
