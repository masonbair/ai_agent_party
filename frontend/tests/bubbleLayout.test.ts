import { describe, it, expect } from 'vitest';
import { computeBubbleOffsets } from '../src/components/bubbleLayout';

describe('computeBubbleOffsets', () => {
  it('gives non-overlapping bubbles a zero offset', () => {
    const offsets = computeBubbleOffsets([
      { id: 'a', x: 100, y: 100 },
      { id: 'b', x: 600, y: 100 },
    ]);
    expect(offsets.a).toBe(0);
    expect(offsets.b).toBe(0);
  });

  it('stacks bubbles whose anchors are close together', () => {
    const offsets = computeBubbleOffsets([
      { id: 'a', x: 100, y: 100 },
      { id: 'b', x: 120, y: 110 }, // close in both axes
    ]);
    // One stays at base, the other is lifted by at least one level.
    const lifted = [offsets.a, offsets.b].filter((o) => o > 0);
    expect(lifted.length).toBe(1);
    expect(Math.max(offsets.a, offsets.b)).toBeGreaterThanOrEqual(34);
  });
});
