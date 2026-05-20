import type { Participant } from '../api/types';

type ReactionState = { emoji: string; expiresAt: number };

type Props = {
  reactions: Map<string, ReactionState>;
  participants: Participant[];
  worldWidth?: number;
  worldHeight?: number;
};

export function ReactionLayer({
  reactions,
  participants,
  worldWidth,
  worldHeight,
}: Props) {
  return (
    <>
      {participants.map((p) => {
        const r = reactions.get(p.id);
        if (!r) return null;
        const leftStyle =
          worldWidth ? `${(p.x / worldWidth) * 100}%` : p.x;
        const topStyle =
          worldHeight ? `${(p.y / worldHeight) * 100}%` : p.y;
        return (
          <div
            key={p.id}
            className="reaction-float"
            style={{
              position: 'absolute',
              left: leftStyle,
              top: topStyle,
              transform: 'translate(-50%, calc(-50% - 34px))',
              pointerEvents: 'none',
              fontSize: 28,
              lineHeight: 1,
              textShadow: '0 2px 6px rgba(0,0,0,0.35)',
              transition: 'left 150ms linear, top 150ms linear',
            }}
          >
            {r.emoji}
          </div>
        );
      })}
    </>
  );
}
