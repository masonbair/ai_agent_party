import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { LightingOverlay } from '../src/components/LightingOverlay';

describe('LightingOverlay', () => {
  it('applies a different tint per preset', () => {
    const { container, rerender } = render(<LightingOverlay preset="day" />);
    const dayBg = (container.firstChild as HTMLElement).style.backgroundColor;
    rerender(<LightingOverlay preset="night" />);
    const nightBg = (container.firstChild as HTMLElement).style.backgroundColor;
    expect(dayBg).not.toBe(nightBg);
  });
});
