import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PartyPeekModal from '../src/components/PartyPeekModal';

const previewResponse = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  occupancy: { humans: 2, agents: 3, total: 5, active_last_5min: 4 },
  lighting: 'dusk',
  music: { url: null, label: 'Lo-fi' },
  recent_chat: [
    { seq: 1, actor_id: 'h1', actor_username: 'alice', actor_kind: 'human', text: 'hello world', at: 1.0 },
    { seq: 2, actor_id: 'a1', actor_username: 'bot1', actor_kind: 'agent', text: 'hi back', at: 2.0 },
  ],
};

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('PartyPeekModal', () => {
  beforeEach(() => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const u = String(url);
      if (u.endsWith('/api/parties/cream-terrazzo/preview')) {
        return jsonResponse(previewResponse);
      }
      return new Response('not found', { status: 404 });
    });
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches and renders the preview payload', async () => {
    render(<PartyPeekModal slug="cream-terrazzo" onClose={() => {}} />);
    expect(await screen.findByText(/2 humans/i)).toBeInTheDocument();
    expect(screen.getByText(/3 agents/i)).toBeInTheDocument();
    expect(screen.getByText(/4 active/i)).toBeInTheDocument();
    expect(screen.getByText(/lighting:\s*dusk/i)).toBeInTheDocument();
    expect(screen.getByText(/music:\s*Lo-fi/i)).toBeInTheDocument();
    expect(screen.getByText(/alice:\s*hello world/i)).toBeInTheDocument();
    expect(screen.getByText(/bot1:\s*hi back/i)).toBeInTheDocument();
  });

  it('renders an empty-state when no recent chat', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ ...previewResponse, recent_chat: [] }),
    );
    render(<PartyPeekModal slug="cream-terrazzo" onClose={() => {}} />);
    expect(await screen.findByText(/no recent chat/i)).toBeInTheDocument();
  });

  it('calls onClose when the close button is clicked', async () => {
    const onClose = vi.fn();
    render(<PartyPeekModal slug="cream-terrazzo" onClose={onClose} />);
    await waitFor(() => screen.getByText(/Cream Terrazzo Lounge/));
    await userEvent.click(screen.getByRole('button', { name: /close/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('shows an error when the fetch fails', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      new Response('boom', { status: 500 }),
    );
    render(<PartyPeekModal slug="cream-terrazzo" onClose={() => {}} />);
    expect(await screen.findByText(/couldn't load preview/i)).toBeInTheDocument();
  });
});
