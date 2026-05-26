import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { ModuleStructure } from '../src/components/modules/ModuleStructure';

const stickyMod = {
  id: 'sticky-1',
  kind: 'stickynotes' as const,
  x: 20,
  y: 410,
  w: 180,
  h: 70,
  interactionRect: { x: -4, y: 386, w: 228, h: 118 },
  approachSlots: [],
  notes: [],
};

describe('ModuleStructure', () => {
  it('renders a label for note board', () => {
    render(<ModuleStructure mod={stickyMod} inZone={false} onOpen={() => {}} />);
    expect(screen.getByText(/NOTE BOARD/i)).toBeInTheDocument();
  });

  it('invokes onOpen only when in range', () => {
    const onOpen = vi.fn();
    const { rerender } = render(
      <ModuleStructure mod={stickyMod} inZone={false} onOpen={onOpen} />,
    );
    fireEvent.click(screen.getByTestId('module-structure-sticky-1'));
    expect(onOpen).not.toHaveBeenCalled();

    rerender(<ModuleStructure mod={stickyMod} inZone={true} onOpen={onOpen} />);
    fireEvent.click(screen.getByTestId('module-structure-sticky-1'));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
