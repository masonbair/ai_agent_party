import { describe, expect, it } from 'vitest';
import { PARTIES } from '../src/parties/registry';

describe('frontend party registry', () => {
  it('includes cream-terrazzo with the three named zones', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo');
    expect(ct).toBeDefined();
    const zoneIds = new Set(ct!.zones.map((z) => z.id));
    expect(zoneIds).toEqual(new Set(['dance', 'chill', 'snacks']));
  });

  it('marks music as a placeholder', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo')!;
    expect(ct.music.url).toBeNull();
  });

  it('defines a room with walls and a border', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo')!;
    expect(ct.room.border).toMatch(/^\d+px /);
    expect(ct.room.walls.length).toBeGreaterThan(0);
  });

  it('every zone has solid fill and a border color', () => {
    const ct = PARTIES.find((p) => p.slug === 'cream-terrazzo')!;
    for (const z of ct.zones) {
      expect(z.color.startsWith('#')).toBe(true);
      expect(z.borderColor.startsWith('#')).toBe(true);
    }
  });
});
