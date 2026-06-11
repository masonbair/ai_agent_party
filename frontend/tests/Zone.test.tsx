import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import Zone from '../src/components/Zone';

const zone = {
  id: 'dance',
  label: 'DANCE',
  x: 6.0,
  y: 8.0,
  width: 34.0,
  height: 36.0,
  color: '#ff6b9d',
  labelColor: '#ffffff',
  borderColor: '#8b1a4a',
};

describe('Zone', () => {
  it('renders as a boxy element with id-based aria-label', () => {
    render(<Zone zone={zone} />);
    const el = screen.getByLabelText('zone-dance');
    expect(el).toBeInTheDocument();
  });

  it('places the label text inside', () => {
    render(<Zone zone={zone} />);
    expect(screen.getByText('DANCE')).toBeInTheDocument();
  });

  it('uses percent-based positioning from zone coords', () => {
    render(<Zone zone={zone} />);
    const el = screen.getByLabelText('zone-dance') as HTMLElement;
    expect(el.style.left).toBe('6%');
    expect(el.style.top).toBe('8%');
    expect(el.style.width).toBe('34%');
    expect(el.style.height).toBe('36%');
  });

  it('uses solid fill color and a chunky ink border', () => {
    render(<Zone zone={zone} />);
    const el = screen.getByLabelText('zone-dance') as HTMLElement;
    expect(el.style.background).toContain('rgb(255, 107, 157)');
    // Memphis Pop: zones use a uniform thick ink border, not per-zone borderColor.
    expect(el.style.border).toContain('3px solid');
    expect(el.style.border).toContain('var(--op-ink)');
  });
});
