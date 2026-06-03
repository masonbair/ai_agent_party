type Props = {
  label: string;
  trackId?: string | null;
};

export default function MusicPill({ label, trackId }: Props) {
  const display = trackId ? trackId : label;
  return (
    <div
      style={{
        position: 'absolute',
        top: 12,
        right: 12,
        padding: '4px 10px',
        background: 'rgba(0,0,0,0.6)',
        color: '#fff',
        borderRadius: 999,
        fontSize: 12,
      }}
    >
      🎵 {display}
    </div>
  );
}
