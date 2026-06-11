import type { ThreadSummary } from '../api/dm';

type Props = {
  threads: ThreadSummary[];
  unreadCount: (thread_key: string) => number;
  onOpen: (thread_key: string) => void;
};

export default function DmThreadList({ threads, unreadCount, onOpen }: Props) {
  if (threads.length === 0) {
    return (
      <p
        style={{
          padding: 24,
          color: 'var(--op-muted)',
          fontFamily: 'var(--op-font-mono)',
          fontSize: 13,
          textAlign: 'center',
        }}
      >
        No threads yet — open a DM by clicking someone's avatar.
      </p>
    );
  }
  return (
    <ul
      style={{
        listStyle: 'none',
        padding: 0,
        margin: 0,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {threads.map((t) => {
        const unread = unreadCount(t.thread_key);
        return (
          <li key={t.thread_key}>
            <button
              type="button"
              onClick={() => onOpen(t.thread_key)}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '13px 16px',
                background: 'transparent',
                border: 'none',
                borderBottom: '2px solid var(--op-ink)',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span style={{ flex: 1, overflow: 'hidden' }}>
                <strong style={{ display: 'block', fontWeight: 800 }}>
                  {t.last_sender_name}
                </strong>
                <span
                  style={{
                    color: 'var(--op-muted)',
                    fontFamily: 'var(--op-font-mono)',
                    fontSize: 12,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: 'block',
                  }}
                >
                  {t.last_text}
                </span>
              </span>
              {unread > 0 ? (
                <span
                  aria-label={`${unread} unread`}
                  style={{
                    background: 'var(--op-coral)',
                    color: '#fff',
                    border: '2px solid var(--op-ink)',
                    borderRadius: 999,
                    padding: '0 7px',
                    fontSize: 12,
                    fontWeight: 800,
                    lineHeight: '20px',
                    minWidth: 22,
                    height: 22,
                    textAlign: 'center',
                    alignSelf: 'center',
                  }}
                >
                  {unread}
                </span>
              ) : null}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
