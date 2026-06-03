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
  // Keep the bubble at its natural content width by shifting its anchor as
  // the avatar approaches a wall. The wider safe-zones (was 18/82, now 30/70)
  // let the bubble flip BEFORE it would have to wrap to fit. Anchor
  // 'translate-x: 0%' means left edge at avatar (extends right); '-100%'
  // means right edge at avatar (extends left); '-50%' is centered.
  const translateX = leftPct < 30 ? '0%' : leftPct > 70 ? '-100%' : '-50%';
  return (
    <div
      data-fading={fading ? 'true' : undefined}
      style={{
        position: 'absolute',
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: `translate(${translateX}, calc(-100% - 28px))`,
        pointerEvents: 'none',
        background: 'rgba(255,255,255,0.95)',
        color: '#2a2a2a',
        border: '1px solid #c9b58a',
        borderRadius: 10,
        padding: '3px 8px',
        fontSize: 12,
        boxShadow: '0 2px 4px rgba(0,0,0,0.12)',
        // ``width: max-content`` makes the bubble grow to fit its text rather
        // than shrinking to whatever inline-size the containing block leaves
        // available. Combined with maxWidth: 260 this gives the natural
        // one-line look until the text genuinely exceeds 260px.
        width: 'max-content',
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
