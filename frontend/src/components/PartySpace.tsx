import { useRef } from 'react';
import type { Participant, PartyConfig, User } from '../api/types';
import { useMovement } from '../hooks/useMovement';
import Avatar from './Avatar';
import ChatBubble from './ChatBubble';
import ChatInput from './ChatInput';
import MusicPill from './MusicPill';
import Wall from './Wall';
import Zone from './Zone';

const SPEED = 220; // logical units / sec

type Props = {
  party: PartyConfig;
  user: User;
  participants?: Participant[];
  onMove?: (x: number, y: number) => void;
  bubbles?: Record<string, { text: string; expiresAt: number }>;
  slug: string;
  principal: { kind: 'human' | 'agent'; id: string };
  status: 'connecting' | 'open' | 'closed';
};

export default function PartySpace({
  party,
  user,
  participants,
  onMove,
  bubbles,
  slug,
  principal,
  status,
}: Props) {
  const { width, height } = party.worldSize;
  const { position, setTarget } = useMovement({
    worldWidth: width,
    worldHeight: height,
    speed: SPEED,
    walls: party.room.walls,
    onMove,
    moveThrottleMs: 100,
  });
  const floorRef = useRef<HTMLDivElement>(null);

  function onClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = floorRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    const logicalX = ((e.clientX - rect.left) / rect.width) * width;
    const logicalY = ((e.clientY - rect.top) / rect.height) * height;
    setTarget({ x: logicalX, y: logicalY });
  }

  // If participants is provided and non-empty, render everyone (overriding the
  // local-only view). The local user's x/y is overridden with the hook's
  // `position` so the local avatar stays visually responsive even before the
  // server echoes a move. Otherwise fall back to the single-player path:
  // render only the local user.
  const renderList: Participant[] =
    participants && participants.length > 0
      ? participants.map((p) =>
          p.id === user.session_id ? { ...p, x: position.x, y: position.y } : p,
        )
      : [
          {
            id: user.session_id,
            kind: 'human' as const,
            username: user.username,
            color: user.color,
            x: position.x,
            y: position.y,
          },
        ];

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
        {renderList.map((p) => (
          <Avatar
            key={p.id}
            username={p.username}
            color={p.color}
            x={p.x}
            y={p.y}
            worldWidth={width}
            worldHeight={height}
            variant={p.id === user.session_id ? 'self' : 'other'}
          />
        ))}
        <MusicPill label={party.music.label} />
        {Object.entries(bubbles ?? {}).map(([participantId, bubble]) => {
          const speaker = renderList.find((p) => p.id === participantId);
          if (!speaker) return null;
          return (
            <ChatBubble
              key={participantId}
              text={bubble.text}
              x={speaker.x}
              y={speaker.y}
              worldWidth={width}
              worldHeight={height}
              expiresAt={bubble.expiresAt}
            />
          );
        })}
        <ChatInput slug={slug} principal={principal} disabled={status !== 'open'} />
      </div>
    </div>
  );
}
