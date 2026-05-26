import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { DrawBoard } from '../src/components/modules/DrawBoard';

const mod = {
  id: 'draw-1',
  kind: 'drawboard' as const,
  x: 0,
  y: 0,
  w: 200,
  h: 100,
  interactionRect: { x: -24, y: -24, w: 248, h: 148 },
  approachSlots: [],
  strokes: [],
  vote: { votes: 0, needed: 1 },
};

describe('DrawBoard', () => {
  it('shows clear button with vote tally', () => {
    render(
      <DrawBoard
        mod={mod}
        principal={{ kind: 'human', id: 'p1' }}
        slug="s"
        inZone={true}
      />,
    );
    expect(
      screen.getByRole('button', { name: /clear/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/0\s*\/\s*1/)).toBeInTheDocument();
  });

  it('disables interactions when not in zone', () => {
    render(
      <DrawBoard
        mod={mod}
        principal={{ kind: 'human', id: 'p1' }}
        slug="s"
        inZone={false}
      />,
    );
    const btn = screen.getByRole('button', {
      name: /clear/i,
    }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
});
