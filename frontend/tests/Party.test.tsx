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
