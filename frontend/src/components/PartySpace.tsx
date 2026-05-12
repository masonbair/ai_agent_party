import { useRef } from 'react';
import type { PartyConfig, User } from '../api/types';
import { useMovement } from '../hooks/useMovement';
import Avatar from './Avatar';
import MusicPill from './MusicPill';
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
    if (!rect) return;
    setTarget({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }

  return (
    <div
      ref={floorRef}
      onClick={onClick}
      style={{
        position: 'relative',
        width,
        height,
        background: party.theme.floor,
        borderRadius: 16,
        overflow: 'hidden',
        margin: '24px auto',
        boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
        cursor: 'pointer',
        userSelect: 'none',
      }}
    >
      {party.zones.map((z) => (
        <Zone key={z.id} zone={z} worldWidth={width} worldHeight={height} />
      ))}
      <Avatar username={user.username} color={user.color} x={position.x} y={position.y} />
      <MusicPill label={party.music.label} />
    </div>
  );
}
