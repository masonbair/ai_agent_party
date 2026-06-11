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
  displayNameOverride?: string;
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
  displayNameOverride,
}: Props) {
  useEffect(() => {
    onMarkRead();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const otherFromMessages = messages.find(
    (m) => `${m.sender_kind}:${m.sender_id}` !== selfPrincipalKey,
  )?.sender_name;
  const otherFromSummary =
    thread &&
    `${thread.last_sender_kind}:${thread.last_sender_id}` !== selfPrincipalKey
      ? thread.last_sender_name
      : undefined;
  const otherName =
    displayNameOverride ??
    otherFromMessages ??
    otherFromSummary ??
    'Direct message';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <header
        style={{
          padding: '12px 16px',
          borderBottom: '3px solid var(--op-ink)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}
      >
        <button
          type="button"
          onClick={onBack}
          aria-label="Back to thread list"
          style={{
            width: 30,
            height: 30,
            borderRadius: 999,
            background: 'var(--op-paper)',
            border: '3px solid var(--op-ink)',
            boxShadow: '2px 2px 0 var(--op-shadow)',
            fontSize: 16,
            fontWeight: 900,
            lineHeight: 1,
            cursor: 'pointer',
            color: 'var(--op-ink)',
            padding: 0,
            flexShrink: 0,
          }}
        >
          ←
        </button>
        <strong style={{ fontSize: 17, fontWeight: 900, letterSpacing: '-0.3px' }}>
          {otherName}
        </strong>
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
                background: mine ? 'var(--op-coral)' : 'var(--op-paper-2)',
                color: 'var(--op-ink)',
                border: '2px solid var(--op-ink)',
                boxShadow: '2px 2px 0 var(--op-shadow)',
                padding: '7px 11px',
                borderRadius: 'var(--op-radius-sm)',
                maxWidth: '80%',
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--op-font-mono)',
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: 0.3,
                  opacity: 0.75,
                  marginBottom: 1,
                }}
              >
                {m.sender_name}
              </div>
              <div style={{ fontWeight: 600 }}>{m.text}</div>
            </div>
          );
        })}
      </div>
      <DmComposer onSend={onSend} sendError={sendError} autoFocus />
    </div>
  );
}
