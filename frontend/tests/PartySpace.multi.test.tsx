import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PartySpace from '../src/components/PartySpace';
import type { Participant, PartyConfig, User } from '../src/api/types';

const party: PartyConfig = {
  slug: 'cream-terrazzo',
  name: 'Cream Terrazzo Lounge',
  description: 'A bright, friendly room.',
  theme: { floor: '#f4ead5', accent: '#ff6b9d' },
  zones: [],
  music: { url: null, label: 'Music coming soon' },
  worldSize: { width: 800, height: 500 },
  room: { clipPath: null, border: '6px solid #8b6f47', borderRadius: 12, walls: [] },
};

const selfUser: User = { session_id: 'sid-1', username: 'alice', color: '#ff6b9d' };

const participants: Participant[] = [
  { id: 'sid-1', kind: 'human', username: 'alice', color: '#ff6b9d', x: 200, y: 200 },
  { id: 'sid-2', kind: 'human', username: 'bob', color: '#4dd0e1', x: 400, y: 300 },
];

const selfPrincipal = { kind: 'human' as const, id: 'sid-1' };

describe('PartySpace with multiple participants', () => {
  it('renders one avatar per participant and marks the local user', () => {
    const { container } = render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={participants}
        slug={party.slug}
        principal={selfPrincipal}
        status="open"
      />,
    );
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
    const selves = container.querySelectorAll('[data-self="true"]');
    expect(selves.length).toBe(1);
  });

  it('falls back to local-only render when participants is undefined', () => {
    const { container } = render(
      <PartySpace
        party={party}
        user={selfUser}
        slug={party.slug}
        principal={selfPrincipal}
        status="open"
      />,
    );
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.queryByText('bob')).not.toBeInTheDocument();
    const selves = container.querySelectorAll('[data-self="true"]');
    expect(selves.length).toBe(1);
  });
});

describe('PartySpace — chat bubbles & input', () => {
  it('renders a bubble for each entry in bubbles, anchored to participant position', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={participants}
        bubbles={{ 'sid-2': { text: 'hello', expiresAt: Date.now() + 5000 } }}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="open"
      />,
    );
    expect(screen.getByText('hello')).toBeInTheDocument();
  });

  it('does not render a bubble for a participant no longer in the list', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={[]}
        bubbles={{ ghost: { text: 'lost', expiresAt: Date.now() + 5000 } }}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="open"
      />,
    );
    expect(screen.queryByText('lost')).not.toBeInTheDocument();
  });

  it('passes speaker color to the chat bubble border', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={participants}
        bubbles={{ 'sid-2': { text: 'hello', expiresAt: Date.now() + 5000 } }}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="open"
      />,
    );
    const bubble = screen.getByText('hello').parentElement!;
    expect(bubble.style.border).toMatch(/77, 208, 225|#4dd0e1/);
  });

  it('mounts a chat input', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={[]}
        bubbles={{}}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="open"
      />,
    );
    expect(screen.getByPlaceholderText(/say something/i)).toBeInTheDocument();
  });

  it('disables the input when status is not open', () => {
    render(
      <PartySpace
        party={party}
        user={selfUser}
        participants={[]}
        bubbles={{}}
        slug={party.slug}
        principal={{ kind: 'human', id: 'sid-1' }}
        status="connecting"
      />,
    );
    const input = screen.getByRole('textbox') as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});
