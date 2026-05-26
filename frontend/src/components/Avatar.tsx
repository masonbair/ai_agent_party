type Props = {
  username: string;
  color: string;
  x: number;            // logical coord
  y: number;            // logical coord
  worldWidth: number;
  worldHeight: number;
  variant?: 'self' | 'other';
  onSelect?: () => void;
};

export default function Avatar({
  username,
  color,
  x,
  y,
  worldWidth,
  worldHeight,
  variant = 'other',
  onSelect,
}: Props) {
  const leftPct = (x / worldWidth) * 100;
  const topPct = (y / worldHeight) * 100;
  return (
    <div
      data-self={variant === 'self' ? 'true' : undefined}
      style={{
        position: 'absolute',
        left: `${leftPct}%`,
        top: `${topPct}%`,
        transform: 'translate(-50%, -50%)',
        pointerEvents: onSelect ? 'auto' : 'none',
        transition: 'left 150ms linear, top 150ms linear',
      }}
    >
      <div
        style={{
          position: 'absolute',
          bottom: 28,
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 12,
          background: 'rgba(255,255,255,0.9)',
          padding: '1px 6px',
          borderRadius: 8,
          whiteSpace: 'nowrap',
          fontWeight: 600,
          pointerEvents: 'none',
        }}
      >
        {username}
      </div>
      <button
        type="button"
        aria-label={onSelect ? `Direct message ${username}` : username}
        onClick={(e) => {
          if (!onSelect) return;
          e.stopPropagation();
          onSelect();
        }}
        disabled={!onSelect}
        style={{
          width: 28,
          height: 28,
          padding: 0,
          borderRadius: '50%',
          background: color,
          border: '2px solid white',
          cursor: onSelect ? 'pointer' : 'default',
          boxShadow:
            variant === 'self'
              ? '0 2px 6px rgba(0,0,0,0.25), inset 0 0 0 2px rgba(255,255,255,0.8)'
              : '0 2px 6px rgba(0,0,0,0.25)',
        }}
      />
    </div>
  );
}
