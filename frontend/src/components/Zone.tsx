import type { Zone as ZoneType } from '../api/types';

type Props = { zone: ZoneType; worldWidth: number; worldHeight: number };

export default function Zone({ zone, worldWidth, worldHeight }: Props) {
  const widthPx = (zone.width / 100) * worldWidth;
  const heightPx = (zone.height / 100) * worldHeight;
  const leftPx = (zone.x / 100) * worldWidth - widthPx / 2;
  const topPx = (zone.y / 100) * worldHeight - heightPx / 2;

  return (
    <div
      aria-label={`zone-${zone.id}`}
      style={{
        position: 'absolute',
        left: leftPx,
        top: topPx,
        width: widthPx,
        height: heightPx,
        background: `radial-gradient(ellipse at center, ${zone.color}, transparent 70%)`,
        borderRadius: '50%',
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: '50%',
          transform: 'translateX(-50%)',
          color: zone.labelColor,
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: 1,
        }}
      >
        {zone.label}
      </div>
    </div>
  );
}
