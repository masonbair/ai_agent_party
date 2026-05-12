import type { PartyConfig } from '../api/types';
import Wall from './Wall';
import Zone from './Zone';

type Props = { party: PartyConfig };

export default function PartyPreview({ party }: Props) {
  const { width, height } = party.worldSize;
  return (
    <div
      style={{
        width: '100%',
        aspectRatio: `${width} / ${height}`,
        position: 'relative',
      }}
      aria-label={`preview-${party.slug}`}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: party.theme.floor,
          border: party.room.border,
          borderRadius: party.room.borderRadius ?? 0,
          clipPath: party.room.clipPath ?? 'none',
          overflow: 'hidden',
          pointerEvents: 'none',
        }}
      >
        {party.zones.map((z) => (
          <Zone key={z.id} zone={z} />
        ))}
        {party.room.walls.map((w, i) => (
          <Wall key={i} wall={w} />
        ))}
      </div>
    </div>
  );
}
