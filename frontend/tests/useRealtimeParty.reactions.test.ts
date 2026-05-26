import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useRealtimeParty } from '../src/hooks/useRealtimeParty';
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

const selfPrincipal: Principal = { kind: 'human', id: 'p1' };

describe('useRealtimeParty reactions', () => {
  it('inserts a reaction on a reaction event', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 's', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances.at(-1)!;
    await act(async () => {
      ws.receive({
        type: 'event',
        cursor: 1,
        event: {
          type: 'reaction',
          seq: 1,
          actor_id: 'p2',
          emoji: 'heart',
          expires_at: Date.now() / 1000 + 1,
          at: Date.now() / 1000,
        },
      });
    });
    expect(result.current.reactions.get('p2')?.emoji).toBe('heart');
  });

  it('updates lighting on lighting_changed event', async () => {
    const { result } = renderHook(() =>
      useRealtimeParty({ slug: 's', principal: selfPrincipal }),
    );
    await act(async () => {
      await Promise.resolve();
    });
    const ws = MockWebSocket.instances.at(-1)!;
    await act(async () => {
      ws.receive({
        type: 'event',
        cursor: 2,
        event: { type: 'lighting_changed', seq: 2, preset: 'night' },
      });
    });
    expect(result.current.lighting).toBe('night');
  });
});
