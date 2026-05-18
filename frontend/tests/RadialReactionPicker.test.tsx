import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import { RadialReactionPicker } from '../src/components/RadialReactionPicker';

describe('RadialReactionPicker', () => {
  it('does not render when closed', () => {
    render(
      <RadialReactionPicker
        open={false}
        anchorPercent={{ x: 50, y: 50 }}
        onPick={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.queryByTestId('radial-reaction-picker')).toBeNull();
  });

  it('renders 12 emoji buttons when open', () => {
    render(
      <RadialReactionPicker
        open={true}
        anchorPercent={{ x: 50, y: 50 }}
        onPick={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.getAllByRole('menuitem')).toHaveLength(12);
  });

  it('commits the selected emoji on Enter and closes', () => {
    const onPick = vi.fn();
    const onClose = vi.fn();
    render(
      <RadialReactionPicker
        open={true}
        anchorPercent={{ x: 50, y: 50 }}
        onPick={onPick}
        onClose={onClose}
      />,
    );
    fireEvent.keyDown(window, { key: 'Enter' });
    expect(onPick).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(
      <RadialReactionPicker
        open={true}
        anchorPercent={{ x: 50, y: 50 }}
        onPick={() => {}}
        onClose={onClose}
      />,
    );
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('clicking a button picks that emoji and closes', () => {
    const onPick = vi.fn();
    const onClose = vi.fn();
    render(
      <RadialReactionPicker
        open={true}
        anchorPercent={{ x: 50, y: 50 }}
        onPick={onPick}
        onClose={onClose}
      />,
    );
    const items = screen.getAllByRole('menuitem');
    fireEvent.click(items[3]);
    expect(onPick).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
