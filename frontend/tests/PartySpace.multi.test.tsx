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

describe('PartySpace with multiple participants', () => {
  it('renders one avatar per participant and marks the local user', () => {
    const { container } = render(
      <PartySpace party={party} user={selfUser} participants={participants} />,
    );
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
    const selves = container.querySelectorAll('[data-self="true"]');
    expect(selves.length).toBe(1);
  });

  it('falls back to local-only render when participants is undefined', () => {
    const { container } = render(<PartySpace party={party} user={selfUser} />);
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.queryByText('bob')).not.toBeInTheDocument();
    const selves = container.querySelectorAll('[data-self="true"]');
    expect(selves.length).toBe(1);
  });
});
