type Props = {
  unreadCount: number;
  onClick: () => void;
};

export default function InboxButton({ unreadCount, onClick }: Props) {
  return (
    <button
      type="button"
      aria-label="Open direct messages"
      onClick={onClick}
      style={{
        position: 'relative',
        fontFamily: 'var(--op-font-display)',
        background: 'var(--op-paper)',
        border: '3px solid var(--op-ink)',
        color: 'var(--op-ink)',
        padding: '8px 16px',
        borderRadius: 999,
        fontSize: 14,
        fontWeight: 800,
        cursor: 'pointer',
        boxShadow: '3px 3px 0 var(--op-shadow)',
      }}
    >
      Inbox
      {unreadCount > 0 ? (
        <span
          data-testid="inbox-unread-badge"
          style={{
            position: 'absolute',
            top: -8,
            right: -8,
            background: 'var(--op-coral)',
            color: 'white',
            border: '2px solid var(--op-ink)',
            borderRadius: 999,
            padding: '0 6px',
            fontSize: 11,
            fontWeight: 800,
            lineHeight: '18px',
            minWidth: 20,
            textAlign: 'center',
          }}
        >
          {unreadCount}
        </span>
      ) : null}
    </button>
  );
}
