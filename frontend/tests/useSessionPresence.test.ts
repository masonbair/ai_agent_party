import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSessionPresence } from '../src/hooks/useSessionPresence';

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

describe('useSessionPresence', () => {
  it('opens a WS and sends auth with the session_id', async () => {
    renderHook(() => useSessionPresence({ sessionId: 'sid-1' }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain('/api/session/ws');
    expect(JSON.parse(ws.sent[0])).toEqual({ type: 'auth', session_id: 'sid-1' });
  });

  it('does not open a WS when sessionId is null', async () => {
    renderHook(() => useSessionPresence({ sessionId: null }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it('invokes onEvicted, closes, and suppresses reconnect on an evicted frame', async () => {
    const onEvicted = vi.fn();
    renderHook(() => useSessionPresence({ sessionId: 'sid-1', onEvicted }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];

    act(() => ws.receive({ type: 'evicted', reason: 'takeover' }));

    expect(onEvicted).toHaveBeenCalledTimes(1);
    expect(ws.readyState).toBe(MockWebSocket.CLOSED);

    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('invokes onEvicted and suppresses reconnect on a server error frame', async () => {
    const onEvicted = vi.fn();
    renderHook(() => useSessionPresence({ sessionId: 'sid-1', onEvicted }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];

    act(() => ws.receive({ type: 'error', detail: 'invalid session' }));

    expect(onEvicted).toHaveBeenCalledTimes(1);
    expect(ws.readyState).toBe(MockWebSocket.CLOSED);

    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances).toHaveLength(1);
  });

  it('does not reset backoff on raw onopen (server may still reject auth)', async () => {
    renderHook(() => useSessionPresence({ sessionId: 'sid-1' }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws1 = MockWebSocket.instances[0];

    // First close right after onopen — backoff should grow to 2s on the next cycle.
    act(() => ws1.close());

    // After ~1100ms one reconnect should have fired.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances).toHaveLength(2);
    const ws2 = MockWebSocket.instances[1];

    // Close ws2 immediately after open (auth-reject pattern). Reconnect must
    // wait ~2s now, not 1s. After 1.2s, no new socket yet.
    act(() => ws2.close());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1200));
    });
    expect(MockWebSocket.instances).toHaveLength(2);

    // After total ~2.2s past the second close, a third socket appears.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(3);
  });

  it('reconnects with backoff on an unexpected close', async () => {
    renderHook(() => useSessionPresence({ sessionId: 'sid-1' }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];

    act(() => ws.close());

    await act(async () => {
      await new Promise((r) => setTimeout(r, 1100));
    });
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2);
  });
});
