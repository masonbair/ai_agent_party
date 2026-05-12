type Props = {
  username: string;
  color: string;
  x: number;
  y: number;
};

export default function Avatar({ username, color, x, y }: Props) {
  return (
    <div
      style={{
        position: 'absolute',
        left: x - 12,
        top: y - 12,
        width: 24,
        height: 24,
        pointerEvents: 'none',
        transition: 'left 80ms linear, top 80ms linear',
      }}
    >
      <div
        style={{
          position: 'absolute',
          bottom: 28,
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 12,
          background: 'rgba(255,255,255,0.85)',
          padding: '1px 6px',
          borderRadius: 8,
          whiteSpace: 'nowrap',
        }}
      >
        {username}
      </div>
      <div
        style={{
          width: 24,
          height: 24,
          borderRadius: '50%',
          background: color,
          border: '2px solid white',
          boxShadow: '0 2px 6px rgba(0,0,0,0.2)',
        }}
      />
    </div>
  );
}
