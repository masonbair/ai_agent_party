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
          fontFamily: 'var(--op-font-mono)',
          fontSize: 11,
          background: 'var(--op-ink)',
          color: '#fff',
          padding: '2px 7px',
          borderRadius: 999,
          whiteSpace: 'nowrap',
          fontWeight: 700,
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
          border: '3px solid var(--op-ink)',
          cursor: onSelect ? 'pointer' : 'default',
          boxShadow:
            variant === 'self'
              ? '2px 2px 0 var(--op-shadow), inset 0 0 0 2px rgba(255,255,255,0.85)'
              : '2px 2px 0 var(--op-shadow)',
        }}
      />
    </div>
  );
}
