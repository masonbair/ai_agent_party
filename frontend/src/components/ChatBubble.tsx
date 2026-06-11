// frontend/src/components/ChatBubble.tsx
type Props = {
  text: string;
  x: number;
  y: number;
  worldWidth: number;
  worldHeight: number;
  expiresAt: number;
  color?: string;
  ambient?: boolean;
  /** Extra upward shift (px) applied by the anti-overlap layout. */
  offsetY?: number;
};

const FADE_WINDOW_MS = 500;
const DEFAULT_BORDER = '#1b1714';

export default function ChatBubble({
  text,
  x,
  y,
  worldWidth,
  worldHeight,
  expiresAt,
  color,
  ambient = false,
  offsetY = 0,
}: Props) {
  const leftPct = (x / worldWidth) * 100;
  const topPct = (y / worldHeight) * 100;
  const fading = expiresAt - Date.now() <= FADE_WINDOW_MS;
  const translateX = leftPct < 30 ? '0%' : leftPct > 70 ? '-100%' : '-50%';
  const borderColor = color ?? DEFAULT_BORDER;
  const liftPx = 28 + offsetY;

  if (ambient) {
    // Contentless "someone's talking over there" puff: small, faded, no text.
    return (
      <div
        data-ambient="true"
        data-fading={fading ? 'true' : undefined}
        style={{
          position: 'absolute',
          left: `${leftPct}%`,
          top: `${topPct}%`,
          transform: `translate(-50%, calc(-100% - ${liftPx}px))`,
          pointerEvents: 'none',
          background: '#fff',
          color: 'var(--op-muted)',
          border: `2px dashed ${borderColor}`,
          borderRadius: 12,
          boxShadow: '2px 2px 0 var(--op-shadow)',
          padding: '2px 7px',
          fontSize: 11,
          lineHeight: 1,
          opacity: fading ? 0 : 0.72,
          transition: 'left 150ms linear, top 150ms linear, opacity 400ms ease-out',
          zIndex: 4,
        }}
      >
        <span>···</span>
      </div>
    );
  }

  return (
    <div
      data-fading={fading ? 'true' : undefined}
      style={{
        position: 'absolute',
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: `translate(${translateX}, calc(-100% - ${liftPx}px))`,
        pointerEvents: 'none',
        background: '#fff',
        color: 'var(--op-ink)',
        border: `2px solid ${borderColor}`,
        borderRadius: 12,
        padding: '4px 9px',
        fontSize: 12,
        fontWeight: 600,
        boxShadow: '2px 2px 0 var(--op-shadow)',
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
