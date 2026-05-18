// frontend/src/components/ChatBubble.tsx
type Props = {
  text: string;
  x: number;
  y: number;
  worldWidth: number;
  worldHeight: number;
  expiresAt: number;
};

const FADE_WINDOW_MS = 500;

export default function ChatBubble({
  text,
  x,
  y,
  worldWidth,
  worldHeight,
  expiresAt,
}: Props) {
  const leftPct = (x / worldWidth) * 100;
  const topPct = (y / worldHeight) * 100;
  const fading = expiresAt - Date.now() <= FADE_WINDOW_MS;
  return (
    <div
      data-fading={fading ? 'true' : undefined}
      style={{
        position: 'absolute',
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: 'translate(-50%, calc(-100% - 28px))',
        pointerEvents: 'none',
        background: 'rgba(255,255,255,0.95)',
        color: '#2a2a2a',
        border: '1px solid #c9b58a',
        borderRadius: 10,
        padding: '3px 8px',
        fontSize: 12,
        boxShadow: '0 2px 4px rgba(0,0,0,0.12)',
        maxWidth: 260,
        whiteSpace: 'normal',
        wordBreak: 'break-word',
        display: '-webkit-box',
        WebkitBoxOrient: 'vertical',
        WebkitLineClamp: 2,
        overflow: 'hidden',
        textAlign: 'center',
        lineHeight: 1.3,
        opacity: fading ? 0 : 1,
        transition: 'left 150ms linear, top 150ms linear, opacity 500ms ease-out',
        zIndex: 5,
      }}
    >
      <span>{text}</span>
    </div>
  );
}
