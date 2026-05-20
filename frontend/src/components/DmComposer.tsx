import { useState } from 'react';
import { CHAT_MAX_LEN, validateChatText } from '../api/validation';

const NOT_CO_LOCATED_REASONS: Record<string, string> = {
  not_present: "You're not in any party right now.",
  recipient_not_present: "The other person isn't in any party right now.",
  not_co_located: "You're not at the same party.",
};

type Props = {
  onSend: (text: string) => Promise<void>;
  sendError: string | null;
  disabled?: boolean;
};

export default function DmComposer({ onSend, sendError, disabled }: Props) {
  const [text, setText] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const explanatory =
    sendError && NOT_CO_LOCATED_REASONS[sendError]
      ? NOT_CO_LOCATED_REASONS[sendError]
      : sendError && sendError !== 'send_failed'
      ? sendError
      : null;

  const submit = async () => {
    const result = validateChatText(text);
    if (!result.ok) {
      setLocalError(
        result.reason === 'empty'
          ? 'Type something to send.'
          : result.reason === 'too_long'
          ? `Max ${CHAT_MAX_LEN} characters.`
          : `Only letters, digits, spaces, .,!?'-`,
      );
      return;
    }
    setLocalError(null);
    setSending(true);
    try {
      await onSend(result.text);
      setText('');
    } catch {
      /* sendError will surface from parent */
    } finally {
      setSending(false);
    }
  };

  const disabledForSend = !!explanatory || disabled || sending;

  return (
    <div
      style={{
        padding: 8,
        borderTop: '1px solid rgba(0,0,0,0.08)',
        background: explanatory ? '#f3f3f3' : 'white',
      }}
    >
      {explanatory ? (
        <div
          role="alert"
          style={{ fontSize: 12, color: '#a33', marginBottom: 4 }}
        >
          {explanatory}
        </div>
      ) : null}
      {localError ? (
        <div role="alert" style={{ fontSize: 12, color: '#a33', marginBottom: 4 }}>
          {localError}
        </div>
      ) : null}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!disabledForSend) void submit();
        }}
        style={{ display: 'flex', gap: 6 }}
      >
        <input
          aria-label="DM message"
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabledForSend}
          maxLength={CHAT_MAX_LEN}
          placeholder="Message…"
          style={{ flex: 1, padding: '6px 10px', borderRadius: 6, border: '1px solid #ddd' }}
        />
        <button type="submit" disabled={disabledForSend}>
          Send
        </button>
      </form>
    </div>
  );
}
