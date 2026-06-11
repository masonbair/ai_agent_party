import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { CHAT_MAX_LEN, validateChatText } from '../api/validation';

const NOT_CO_LOCATED_REASONS: Record<string, string> = {
  not_present: "You're not in any party right now.",
  recipient_not_present: "The other person isn't in any party right now.",
  not_co_located: "You're not at the same party.",
};

const dmAlertStyle: CSSProperties = {
  fontFamily: 'var(--op-font-mono)',
  fontSize: 12,
  fontWeight: 700,
  color: 'var(--op-ink)',
  background: 'var(--op-coral)',
  border: '2px solid var(--op-ink)',
  borderRadius: 8,
  padding: '4px 8px',
  marginBottom: 6,
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
      // The textarea is `disabled` while sending, which blurs it. Restore focus
      // so the user can keep typing without re-clicking after each Enter.
      requestAnimationFrame(() => ref.current?.focus());
    }
  };

  const disabledForSend = !!explanatory || disabled || sending;

  return (
    <div
      style={{
        padding: 12,
        borderTop: '3px solid var(--op-ink)',
        background: explanatory ? '#fff3d6' : 'var(--op-paper)',
      }}
    >
      {explanatory ? (
        <div role="alert" style={dmAlertStyle}>
          {explanatory}
        </div>
      ) : null}
      {localError ? (
        <div role="alert" style={dmAlertStyle}>
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
          background: '#fff',
          border: `3px solid ${focused ? 'var(--op-blue)' : 'var(--op-ink)'}`,
          boxShadow: focused
            ? '3px 3px 0 var(--op-blue)'
            : '3px 3px 0 var(--op-shadow)',
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
            fontFamily: 'var(--op-font-display)',
            fontWeight: 600,
            color: 'var(--op-ink)',
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
            background: disabledForSend ? 'var(--op-paper-2)' : 'var(--op-coral)',
            color: 'var(--op-ink)',
            border: '3px solid var(--op-ink)',
            borderRadius: 10,
            padding: '8px 14px',
            fontFamily: 'var(--op-font-display)',
            fontWeight: 900,
            cursor: disabledForSend ? 'not-allowed' : 'pointer',
            boxShadow: disabledForSend ? 'none' : '2px 2px 0 var(--op-shadow)',
            opacity: disabledForSend ? 0.55 : 1,
            transition: 'background 120ms ease',
          }}
        >
          Send
        </button>
      </form>
    </div>
  );
}
