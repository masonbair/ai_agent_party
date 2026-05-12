import { useRef } from 'react';
import type { PartyConfig, User } from '../api/types';
import { useMovement } from '../hooks/useMovement';
import Avatar from './Avatar';
import MusicPill from './MusicPill';
import Wall from './Wall';
import Zone from './Zone';

const SPEED = 220; // logical units / sec

type Props = { party: PartyConfig; user: User };

export default function PartySpace({ party, user }: Props) {
  const { width, height } = party.worldSize;
  const { position, setTarget } = useMovement({
    worldWidth: width,
    worldHeight: height,
    speed: SPEED,
  });
  const floorRef = useRef<HTMLDivElement>(null);

  function onClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = floorRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    const logicalX = ((e.clientX - rect.left) / rect.width) * width;
    const logicalY = ((e.clientY - rect.top) / rect.height) * height;
    setTarget({ x: logicalX, y: logicalY });
  }

  return (
    <div
      style={{
        width: 'min(95vw, 1000px)',
        aspectRatio: `${width} / ${height}`,
        margin: '24px auto',
        position: 'relative',
      }}
    >
      <div
        ref={floorRef}
        onClick={onClick}
        style={{
          position: 'absolute',
          inset: 0,
          background: party.theme.floor,
          border: party.room.border,
          borderRadius: party.room.borderRadius ?? 0,
          clipPath: party.room.clipPath ?? 'none',
          overflow: 'hidden',
          boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        {party.zones.map((z) => (
          <Zone key={z.id} zone={z} />
        ))}
        {party.room.walls.map((w, i) => (
          <Wall key={i} wall={w} />
        ))}
        <Avatar
          username={user.username}
          color={user.color}
          x={position.x}
          y={position.y}
          worldWidth={width}
          worldHeight={height}
        />
        <MusicPill label={party.music.label} />
      </div>
    </div>
  );
}
