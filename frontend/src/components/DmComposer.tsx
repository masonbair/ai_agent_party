import { useEffect, useRef, useState } from 'react';
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
  autoFocus?: boolean;
};

export default function DmComposer({
  onSend,
  sendError,
  disabled,
  autoFocus,
}: Props) {
  const [text, setText] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [focused, setFocused] = useState(false);
  const ref = useRef<HTMLTextAreaElement>(null);

  const explanatory =
    sendError && NOT_CO_LOCATED_REASONS[sendError]
      ? NOT_CO_LOCATED_REASONS[sendError]
      : sendError && sendError !== 'send_failed'
      ? sendError
      : null;

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

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
        padding: 12,
        borderTop: '1px solid rgba(0,0,0,0.06)',
        background: explanatory ? '#faf3f3' : '#fafafa',
      }}
    >
      {explanatory ? (
        <div
          role="alert"
          style={{ fontSize: 12, color: '#a33', marginBottom: 6 }}
        >
          {explanatory}
        </div>
      ) : null}
      {localError ? (
        <div role="alert" style={{ fontSize: 12, color: '#a33', marginBottom: 6 }}>
          {localError}
        </div>
      ) : null}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!disabledForSend) void submit();
        }}
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: 8,
          background: 'white',
          border: `1px solid ${focused ? '#7a5cff' : '#e2e2e6'}`,
          boxShadow: focused
            ? '0 0 0 3px rgba(122, 92, 255, 0.15)'
            : '0 1px 2px rgba(0,0,0,0.03)',
          borderRadius: 14,
          padding: 8,
          transition: 'border-color 120ms ease, box-shadow 120ms ease',
        }}
      >
        <textarea
          ref={ref}
          aria-label="DM message"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (!disabledForSend) void submit();
            }
          }}
          disabled={disabledForSend}
          maxLength={CHAT_MAX_LEN}
          placeholder="Message… (Enter to send, Shift+Enter for newline)"
          rows={1}
          style={{
            flex: 1,
            padding: '8px 10px',
            border: 'none',
            outline: 'none',
            resize: 'none',
            fontFamily: 'inherit',
            fontSize: 14,
            lineHeight: 1.4,
            background: 'transparent',
            maxHeight: 120,
          }}
        />
        <button
          type="submit"
          disabled={disabledForSend}
          aria-label="Send message"
          style={{
            background: disabledForSend ? '#d6d6da' : '#7a5cff',
            color: 'white',
            border: 'none',
            borderRadius: 10,
            padding: '8px 14px',
            fontWeight: 600,
            cursor: disabledForSend ? 'not-allowed' : 'pointer',
            transition: 'background 120ms ease',
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
}
