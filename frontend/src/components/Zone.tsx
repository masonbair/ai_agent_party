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
        border: '3px solid var(--op-ink)',
        borderRadius: 8,
        pointerEvents: 'none',
        boxShadow: '3px 3px 0 var(--op-shadow)',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 6,
          left: 6,
          background: 'var(--op-ink)',
          color: '#fff',
          padding: '2px 7px',
          borderRadius: 999,
          fontFamily: 'var(--op-font-mono)',
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: 1,
        }}
      >
        {zone.label}
      </div>
    </div>
  );
}
