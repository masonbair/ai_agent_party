import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { StickyWall } from '../src/components/modules/StickyWall';

const baseModule = {
  id: 'sticky-1',
  kind: 'stickynotes' as const,
  x: 0,
  y: 0,
  w: 200,
  h: 100,
  interactionRect: { x: -24, y: -24, w: 248, h: 148 },
  approachSlots: [],
  notes: [
    {
      id: 'n1',
      module_id: 'sticky-1',
      author_id: 'p1',
      author_kind: 'human' as const,
      text: 'hi',
      color: 'yellow' as const,
      x: 10,
      y: 10,
      created_at: 0,
    },
  ],
};

describe('StickyWall', () => {
  it('renders existing notes from anywhere', () => {
    render(
      <StickyWall
        mod={baseModule}
        principal={{ kind: 'human', id: 'p2' }}
        slug="s"
        inZone={false}
      />,
    );
    expect(screen.getByText('hi')).toBeInTheDocument();
  });

  it('shows "+ add note" affordance only when in zone', () => {
    const { rerender } = render(
      <StickyWall
        mod={baseModule}
        principal={{ kind: 'human', id: 'p2' }}
        slug="s"
        inZone={false}
      />,
    );
    expect(screen.queryByRole('button', { name: /add note/i })).toBeNull();
    rerender(
      <StickyWall
        mod={baseModule}
        principal={{ kind: 'human', id: 'p2' }}
        slug="s"
        inZone={true}
      />,
    );
    expect(
      screen.getByRole('button', { name: /add note/i }),
    ).toBeInTheDocument();
  });
});
