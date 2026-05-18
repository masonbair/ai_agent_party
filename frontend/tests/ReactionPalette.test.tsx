import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { ReactionPalette } from '../src/components/ReactionPalette';

describe('ReactionPalette', () => {
  it('renders all 12 allowed emoji and fires onSelect', () => {
    const onSelect = vi.fn();
    render(<ReactionPalette onSelect={onSelect} disabled={false} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(12);
    fireEvent.click(buttons[0]);
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(typeof onSelect.mock.calls[0][0]).toBe('string');
  });

  it('disables every button when disabled', () => {
    render(<ReactionPalette onSelect={() => {}} disabled={true} />);
    screen.getAllByRole('button').forEach((b) => {
      expect((b as HTMLButtonElement).disabled).toBe(true);
    });
  });
});
