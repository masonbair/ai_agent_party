import { principalKey } from '../api/dm';
import type { Principal } from '../api/party';
import DmThreadList from './DmThreadList';
import DmThreadView from './DmThreadView';
import type { OpenedThread } from '../hooks/useInbox';
import type { ThreadSummary } from '../api/dm';

type Props = {
  open: boolean;
  onClose: () => void;
  principal: Principal | null;
  threads: ThreadSummary[];
  unreadCount: (thread_key: string) => number;
  openedKey: string | null;
  openedThread: OpenedThread | null;
  onOpenThread: (thread_key: string) => Promise<void>;
  onCloseThread: () => void;
  onMarkRead: (thread_key: string) => void;
  displayNames?: Record<string, string>;
};

export default function DmDrawer({
  open,
  onClose,
  principal,
  threads,
  unreadCount,
  openedKey,
  openedThread,
  onOpenThread,
  onCloseThread,
  onMarkRead,
  displayNames,
}: Props) {
  if (!open) return null;
  const selfKey = principal ? principalKey(principal) : '';
  const activeThread = openedKey
    ? threads.find((t) => t.thread_key === openedKey)
    : undefined;

  return (
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(15, 17, 22, 0.18)',
          zIndex: 99,
        }}
      />
      <aside
        aria-label="Direct messages drawer"
        role="dialog"
        aria-modal="true"
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: 'min(440px, 92vw)',
          background: 'white',
          boxShadow: '-12px 0 32px rgba(0, 0, 0, 0.18)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 100,
          borderLeft: '1px solid rgba(0,0,0,0.06)',
        }}
      >
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '14px 18px',
          borderBottom: '1px solid rgba(0,0,0,0.06)',
        }}
      >
        <strong style={{ fontSize: 16 }}>Direct messages</strong>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close direct messages"
          title="Close (Esc)"
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: 22,
            lineHeight: 1,
            cursor: 'pointer',
            color: '#555',
            padding: 4,
          }}
        >
          ×
        </button>
      </header>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {openedKey && openedThread ? (
          <DmThreadView
            thread={activeThread}
            messages={openedThread.messages}
            onBack={onCloseThread}
            onLoadOlder={openedThread.loadOlder}
            onMarkRead={() => onMarkRead(openedKey)}
            onSend={openedThread.send}
            sendError={openedThread.sendError}
            selfPrincipalKey={selfKey}
            displayNameOverride={displayNames?.[openedKey]}
          />
        ) : (
          <DmThreadList
            threads={threads}
            unreadCount={unreadCount}
            onOpen={onOpenThread}
          />
        )}
      </div>
    </aside>
    </>
  );
}
