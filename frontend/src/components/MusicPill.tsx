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
        padding: '4px 11px',
        background: 'var(--op-ink)',
        color: '#fff',
        border: '2px solid var(--op-ink)',
        borderRadius: 999,
        boxShadow: '2px 2px 0 var(--op-shadow)',
        fontFamily: 'var(--op-font-mono)',
        fontWeight: 700,
        fontSize: 11,
        letterSpacing: 0.3,
      }}
    >
      🎵 {display}
    </div>
  );
}
