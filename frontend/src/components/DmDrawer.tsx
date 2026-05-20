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
    <aside
      aria-label="Direct messages drawer"
      style={{
        position: 'fixed',
        top: 0,
        right: 0,
        bottom: 0,
        width: 'min(360px, 95vw)',
        background: 'white',
        boxShadow: '-4px 0 16px rgba(0,0,0,0.15)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 100,
      }}
    >
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '10px 16px',
          borderBottom: '1px solid rgba(0,0,0,0.06)',
        }}
      >
        <strong>Direct messages</strong>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close direct messages"
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: 20,
            cursor: 'pointer',
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
  );
}
