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
      x: 25,
      y: 25,
      width: 40,
      height: 36,
      color: 'rgba(255,107,157,0.25)',
      labelColor: '#8b1a4a',
    },
  ],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
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

  it('renders party space, zones, avatar, and music placeholder', async () => {
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
