import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

class FakeWS {
  static instances: FakeWS[] = [];
  static SESSION_WS_INSTANCES: FakeWS[] = [];
  url: string;
  readyState = 0;
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: CloseEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  sent: string[] = [];
  constructor(url: string) {
    this.url = url;
    FakeWS.instances.push(this);
    if (url.includes('/api/session/ws')) {
      FakeWS.SESSION_WS_INSTANCES.push(this);
    }
    queueMicrotask(() => {
      this.readyState = 1;
      this.onopen?.(new Event('open'));
    });
  }
  send(payload: string) {
    this.sent.push(payload);
  }
  close() {
    this.readyState = 3;
    this.onclose?.(new CloseEvent('close'));
  }
}

const partyResponse = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  theme: { floor: '#f4ead5', accent: '#ff6b9d' },
  zones: [],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: { clipPath: null, border: '6px solid #8b6f47', borderRadius: 12, walls: [] },
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('App-level session presence', () => {
  beforeEach(() => {
    FakeWS.instances = [];
    FakeWS.SESSION_WS_INSTANCES = [];
    vi.stubGlobal('WebSocket', FakeWS);
    localStorage.setItem('session_id', 'sid-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      const u = String(url);
      const method = (init?.method ?? 'GET').toUpperCase();
      if (u.includes('/api/session/')) {
        return jsonResponse({ session_id: 'sid-1', username: 'Alice', color: '#ff6b9d' });
      }
      if (u.endsWith('/api/parties') && method === 'GET') {
        return jsonResponse({ parties: [partyResponse] });
      }
      if (u.endsWith('/api/parties/cream-terrazzo')) {
        return jsonResponse(partyResponse);
      }
      if (method === 'POST' && u.endsWith('/api/parties/cream-terrazzo/join')) {
        return jsonResponse({
          participant: {
            id: 'sid-1',
            kind: 'human',
            username: 'Alice',
            color: '#ff6b9d',
            x: 100,
            y: 100,
          },
          cursor: 0,
        });
      }
      if (method === 'POST' && u.endsWith('/api/parties/cream-terrazzo/leave')) {
        return new Response(null, { status: 204 });
      }
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('opens exactly one session WS that persists across Lobby -> Party navigation', async () => {
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <App />
      </MemoryRouter>,
    );

    // Wait for Lobby to render.
    await screen.findByText(/Pick a party/);
    expect(FakeWS.SESSION_WS_INSTANCES).toHaveLength(1);
    const sessionWs = FakeWS.SESSION_WS_INSTANCES[0];

    // Click into the party. Lobby unmounts; Party mounts.
    await userEvent.click(
      await screen.findByRole('button', { name: /cream terrazzo lounge/i }),
    );

    // The Party page header should render.
    await screen.findByText(/Cream Terrazzo Lounge/);

    // Still exactly one session WS — the original — never closed.
    expect(FakeWS.SESSION_WS_INSTANCES).toHaveLength(1);
    expect(FakeWS.SESSION_WS_INSTANCES[0]).toBe(sessionWs);
    expect(sessionWs.readyState).toBe(1);
  });
});
