import { useEffect } from 'react';
import type { DmMessage, ThreadSummary } from '../api/dm';
import DmComposer from './DmComposer';

type Props = {
  thread: ThreadSummary | undefined;
  messages: DmMessage[];
  onBack: () => void;
  onLoadOlder: () => Promise<void>;
  onMarkRead: () => void;
  onSend: (text: string) => Promise<void>;
  sendError: string | null;
  selfPrincipalKey: string;
};

export default function DmThreadView({
  thread,
  messages,
  onBack,
  onLoadOlder,
  onMarkRead,
  onSend,
  sendError,
  selfPrincipalKey,
}: Props) {
  useEffect(() => {
    onMarkRead();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const otherName = thread?.last_sender_name ?? 'Direct message';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header
        style={{
          padding: '10px 16px',
          borderBottom: '1px solid rgba(0,0,0,0.06)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to thread list"
          style={{
            background: 'transparent',
            border: 'none',
            fontSize: 18,
            cursor: 'pointer',
          }}
        >
          ←
        </button>
        <strong>{otherName}</strong>
      </header>
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}
        onScroll={(e) => {
          const el = e.currentTarget;
          if (el.scrollTop === 0) {
            void onLoadOlder();
          }
        }}
      >
        {messages.map((m) => {
          const mine = `${m.sender_kind}:${m.sender_id}` === selfPrincipalKey;
          return (
            <div
              key={m.id}
              style={{
                alignSelf: mine ? 'flex-end' : 'flex-start',
                background: mine ? '#ffd2e2' : '#f1f1f1',
                padding: '6px 10px',
                borderRadius: 12,
                maxWidth: '80%',
              }}
            >
              <div style={{ fontSize: 11, color: '#888' }}>{m.sender_name}</div>
              <div>{m.text}</div>
            </div>
          );
        })}
      </div>
      <DmComposer onSend={onSend} sendError={sendError} />
    </div>
  );
}
