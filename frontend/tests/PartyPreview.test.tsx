import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PartyPreview from '../src/components/PartyPreview';

const party = {
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
    ],
  },
};

describe('PartyPreview', () => {
  it('renders zones and walls from the party config', () => {
    render(<PartyPreview party={party} />);
    expect(screen.getByLabelText('zone-dance')).toBeInTheDocument();
    expect(screen.getAllByTestId('wall')).toHaveLength(1);
  });

  it('does not render avatar or music pill', () => {
    render(<PartyPreview party={party} />);
    expect(screen.queryByText(/music coming soon/i)).not.toBeInTheDocument();
  });
});
