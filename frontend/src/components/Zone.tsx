import type { Zone as ZoneType } from '../api/types';

type Props = { zone: ZoneType };

export default function Zone({ zone }: Props) {
  return (
    <div
      aria-label={`zone-${zone.id}`}
      style={{
        position: 'absolute',
        left: `${zone.x}%`,
        top: `${zone.y}%`,
        width: `${zone.width}%`,
        height: `${zone.height}%`,
        background: zone.color,
        border: `3px solid ${zone.borderColor}`,
        borderRadius: 6,
        pointerEvents: 'none',
        boxShadow: '0 2px 6px rgba(0,0,0,0.10)',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          color: zone.labelColor,
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: 1.5,
          textShadow: '0 1px 2px rgba(0,0,0,0.25)',
        }}
      >
        {zone.label}
      </div>
    </div>
  );
}
