import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Lobby from '../src/pages/Lobby';

const sessionResponse = {
  session_id: 'sid-1',
  username: 'Alice',
  color: '#ff6b9d',
};

const partiesResponse = {
  parties: [
    {
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
        walls: [{ x: 50, y: 0, width: 0.75, height: 30, color: '#8b6f47' }],
      },
    },
  ],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('Lobby', () => {
  beforeEach(() => {
    localStorage.setItem('session_id', 'sid-1');
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes('/api/session/')) return jsonResponse(sessionResponse);
      if (u.endsWith('/api/parties')) return jsonResponse(partiesResponse);
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('renders a card per party with a mini preview', async () => {
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <Routes>
          <Route path="/lobby" element={<Lobby />} />
          <Route path="/party/:slug" element={<div>Party page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText(/Cream Terrazzo Lounge/i)).toBeInTheDocument();
    expect(screen.getByLabelText('preview-cream-terrazzo')).toBeInTheDocument();
  });

  it('navigates to /party/:slug when a card is clicked', async () => {
    render(
      <MemoryRouter initialEntries={['/lobby']}>
        <Routes>
          <Route path="/lobby" element={<Lobby />} />
          <Route path="/party/:slug" element={<div>Party page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    const card = await screen.findByRole('button', { name: /cream terrazzo lounge/i });
    await userEvent.click(card);
    expect(await screen.findByText(/Party page/i)).toBeInTheDocument();
  });
});
