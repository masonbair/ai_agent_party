import type { LightingPreset } from '../api/types';

const TINTS: Record<LightingPreset, string> = {
  day: 'rgba(255, 245, 220, 0.05)',
  dusk: 'rgba(120, 60, 140, 0.18)',
  night: 'rgba(20, 30, 80, 0.32)',
  party: 'rgba(255, 80, 200, 0.18)',
};

export function LightingOverlay({ preset }: { preset: LightingPreset }) {
  return (
    <div
      className="lighting-overlay"
      style={{
        position: 'absolute',
        inset: 0,
        backgroundColor: TINTS[preset],
        pointerEvents: 'none',
        mixBlendMode: 'multiply',
        transition: 'background-color 300ms ease',
      }}
    />
  );
}
