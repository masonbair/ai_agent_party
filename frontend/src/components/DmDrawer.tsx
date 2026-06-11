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
          background: 'rgba(27, 23, 20, 0.35)',
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
          background: 'var(--op-paper)',
          boxShadow: '-10px 0 0 var(--op-shadow)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 100,
          borderLeft: '4px solid var(--op-ink)',
        }}
      >
      <header
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 18px',
          borderBottom: '3px solid var(--op-ink)',
        }}
      >
        <strong style={{ fontSize: 18, fontWeight: 900, letterSpacing: '-0.4px' }}>
          Direct messages
        </strong>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close direct messages"
          title="Close (Esc)"
          style={{
            width: 32,
            height: 32,
            borderRadius: 999,
            background: 'var(--op-paper)',
            border: '3px solid var(--op-ink)',
            boxShadow: '2px 2px 0 var(--op-shadow)',
            fontSize: 18,
            fontWeight: 900,
            lineHeight: 1,
            cursor: 'pointer',
            color: 'var(--op-ink)',
            padding: 0,
            flexShrink: 0,
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
