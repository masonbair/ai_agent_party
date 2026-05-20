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
        background: '#fff',
        border: '1px solid rgba(0,0,0,0.1)',
        padding: '6px 14px',
        borderRadius: 999,
        fontSize: 14,
        fontWeight: 600,
        cursor: 'pointer',
        boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
      }}
    >
      Inbox
      {unreadCount > 0 ? (
        <span
          data-testid="inbox-unread-badge"
          style={{
            position: 'absolute',
            top: -6,
            right: -6,
            background: '#ff6b9d',
            color: 'white',
            borderRadius: 999,
            padding: '0 6px',
            fontSize: 11,
            lineHeight: '18px',
            minWidth: 18,
            textAlign: 'center',
          }}
        >
          {unreadCount}
        </span>
      ) : null}
    </button>
  );
}
