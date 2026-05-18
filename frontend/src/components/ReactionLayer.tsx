import type { Participant } from '../api/types';

type ReactionState = { emoji: string; expiresAt: number };

type Props = {
  reactions: Map<string, ReactionState>;
  participants: Participant[];
};

export function ReactionLayer({ reactions, participants }: Props) {
  return (
    <>
      {participants.map((p) => {
        const r = reactions.get(p.id);
        if (!r) return null;
        return (
          <div
            key={p.id}
            className="reaction-float"
            style={{
              position: 'absolute',
              left: p.x,
              top: p.y - 32,
              pointerEvents: 'none',
            }}
          >
            {r.emoji}
          </div>
        );
      })}
    </>
  );
}
