import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Party from '../src/pages/Party';

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
}

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
    MockWebSocket.instances = [];
    vi.stubGlobal('WebSocket', MockWebSocket);
    localStorage.setItem('session_id', 'sid-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      const u = String(url);
      const method = (init?.method ?? 'GET').toUpperCase();
      if (u.includes('/api/session/')) return jsonResponse(sessionResponse);
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
      if (method === 'POST' && u.endsWith('/api/parties/cream-terrazzo/move')) {
        return jsonResponse({ x: 0, y: 0, cursor: 1 });
      }
      if (u.endsWith('/api/parties/cream-terrazzo')) return jsonResponse(partyResponse);
      if (u.endsWith('/api/parties/unknown')) return jsonResponse({ detail: 'nope' }, 404);
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
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

  it('POSTs to /join on mount and /leave on unmount', async () => {
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    const { unmount } = render(
      <MemoryRouter initialEntries={['/party/cream-terrazzo']}>
        <Routes>
          <Route path="/party/:slug" element={<Party />} />
        </Routes>
      </MemoryRouter>,
    );

    // Wait for the party config + join call.
    await screen.findByLabelText('zone-dance');
    await waitFor(() => {
      const calls = fetchSpy.mock.calls;
      const joined = calls.some(
        ([url, init]) =>
          String(url).endsWith('/api/parties/cream-terrazzo/join') &&
          ((init as RequestInit | undefined)?.method ?? 'GET').toUpperCase() === 'POST',
      );
      expect(joined).toBe(true);
    });

    unmount();

    await waitFor(() => {
      const calls = fetchSpy.mock.calls;
      const left = calls.some(
        ([url, init]) =>
          String(url).endsWith('/api/parties/cream-terrazzo/leave') &&
          ((init as RequestInit | undefined)?.method ?? 'GET').toUpperCase() === 'POST',
      );
      expect(left).toBe(true);
    });
  });
});
