import type { ThreadSummary } from '../api/dm';

type Props = {
  threads: ThreadSummary[];
  unreadCount: (thread_key: string) => number;
  onOpen: (thread_key: string) => void;
};

export default function DmThreadList({ threads, unreadCount, onOpen }: Props) {
  if (threads.length === 0) {
    return (
      <p style={{ padding: 24, color: '#888', textAlign: 'center' }}>
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
                padding: '12px 16px',
                background: 'transparent',
                border: 'none',
                borderBottom: '1px solid rgba(0,0,0,0.06)',
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                gap: 8,
              }}
            >
              <span style={{ flex: 1, overflow: 'hidden' }}>
                <strong style={{ display: 'block' }}>
                  {t.last_sender_name}
                </strong>
                <span
                  style={{
                    color: '#666',
                    fontSize: 13,
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
                    background: '#ff6b9d',
                    color: 'white',
                    borderRadius: 999,
                    padding: '0 8px',
                    fontSize: 12,
                    lineHeight: '20px',
                    minWidth: 20,
                    height: 20,
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
