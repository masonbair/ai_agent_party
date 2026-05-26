import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useInbox } from '../src/hooks/useInbox';
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
  send(p: string) {
    this.sent.push(p);
  }
  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close'));
  }
  receive(obj: unknown) {
    this.onmessage?.(new MessageEvent('message', { data: JSON.stringify(obj) }));
  }
}

const me: Principal = { kind: 'human', id: 'me-1' };
const myKey = 'human:me-1';
const tk = ['human:friend', myKey].sort().join('|');

function fetchMock(impl: (url: string) => unknown) {
  return vi.fn(async (url: string) => {
    const body = impl(url);
    return {
      ok: true,
      status: 200,
      json: async () => body,
    } as unknown as Response;
  });
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket);
  localStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('useInbox', () => {
  it('opens a WS to /api/inbox and sends auth', async () => {
    vi.stubGlobal('fetch', fetchMock(() => ({ threads: [] })));
    renderHook(() => useInbox({ principal: me }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    expect(ws.url).toContain('/api/inbox');
    expect(JSON.parse(ws.sent[0])).toEqual({ type: 'auth', principal: me });
  });

  it('upserts a thread on incoming dm frame', async () => {
    vi.stubGlobal('fetch', fetchMock(() => ({ threads: [] })));
    const { result } = renderHook(() => useInbox({ principal: me }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'dm',
        thread_key: tk,
        message: {
          id: 7,
          sender_kind: 'human',
          sender_id: 'friend',
          sender_name: 'Friend',
          text: 'hello',
          at: 1000,
        },
      }),
    );
    expect(result.current.threads).toHaveLength(1);
    expect(result.current.threads[0].last_text).toBe('hello');
  });

  it('derives unread count from localStorage and clears on markRead', async () => {
    vi.stubGlobal('fetch', fetchMock(() => ({ threads: [] })));
    const { result } = renderHook(() => useInbox({ principal: me }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'dm',
        thread_key: tk,
        message: {
          id: 7,
          sender_kind: 'human',
          sender_id: 'friend',
          sender_name: 'Friend',
          text: 'hello',
          at: 1000,
        },
      }),
    );
    expect(result.current.unreadCount(tk)).toBe(1);
    act(() => result.current.markRead(tk));
    expect(result.current.unreadCount(tk)).toBe(0);
    expect(localStorage.getItem(`openparty.dm.lastRead.${tk}`)).toBe('7');
  });

  it('loadOlder calls the history endpoint with before_id', async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      'fetch',
      fetchMock((url) => {
        calls.push(url);
        if (url.includes('/threads/')) {
          return {
            thread_key: tk,
            messages: [
              {
                id: 1,
                sender_kind: 'human',
                sender_id: 'friend',
                sender_name: 'Friend',
                text: 'old',
                at: 50,
              },
            ],
          };
        }
        return { threads: [] };
      }),
    );
    const { result } = renderHook(() => useInbox({ principal: me }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() =>
      ws.receive({
        type: 'dm',
        thread_key: tk,
        message: {
          id: 7,
          sender_kind: 'human',
          sender_id: 'friend',
          sender_name: 'Friend',
          text: 'hello',
          at: 1000,
        },
      }),
    );
    await act(async () => {
      await result.current.openThread(tk);
    });
    // Force loadOlder again to verify before_id usage
    await act(async () => {
      await result.current.openedThread!.loadOlder();
    });
    const historyCalls = calls.filter((u) => u.includes('/threads/'));
    expect(historyCalls.length).toBeGreaterThanOrEqual(1);
    expect(historyCalls.some((u) => u.includes('before_id=7'))).toBe(true);
  });

  it('invokes onEvicted on evicted frame', async () => {
    vi.stubGlobal('fetch', fetchMock(() => ({ threads: [] })));
    const onEvicted = vi.fn();
    renderHook(() => useInbox({ principal: me, onEvicted }));
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances[0];
    act(() => ws.receive({ type: 'evicted', reason: 'takeover' }));
    await waitFor(() => expect(onEvicted).toHaveBeenCalled());
  });
});
