// frontend/src/components/ChatInput.tsx
import { useEffect, useRef, useState } from 'react';
import { chatInParty, type Principal } from '../api/party';
import { ApiError } from '../api/client';
import { CHAT_MAX_LEN, validateChatText } from '../api/validation';

type Props = {
  slug: string;
  principal: Principal;
  disabled: boolean;
};

const REASON_MESSAGES: Record<string, string> = {
  empty: '',
  too_long: `Message too long (max ${CHAT_MAX_LEN} characters)`,
  invalid_chars: 'Message contains disallowed characters',
};

const FOCUS_KEY = 't';

function describeChatError(err: unknown): string {
  if (err instanceof ApiError) {
    const detail = (err.body as { detail?: { error?: string; retry_after_ms?: number } } | null)?.detail;
    if (err.status === 429 && detail?.error === 'rate_limited') {
      const seconds = Math.max(1, Math.ceil((detail.retry_after_ms ?? 0) / 1000));
      return `Slow down — try again in ${seconds}s`;
    }
    if (err.status === 422 && detail?.error === 'invalid_chat_text') {
      return 'That message has disallowed characters or is too long.';
    }
    if (err.status === 404 && detail?.error === 'recipient_unknown') {
      return "Couldn't find that recipient.";
    }
  }
  return 'Failed to send';
}

export default function ChatInput({ slug, principal, disabled }: Props) {
  const [value, setValue] = useState('');
  const [error, setError] = useState<string>('');
  const [sending, setSending] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onWindowKeyDown(e: KeyboardEvent) {
      if (e.key.toLowerCase() !== FOCUS_KEY) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const t = e.target;
      if (t instanceof HTMLElement) {
        if (
          t.isContentEditable ||
          t.tagName === 'INPUT' ||
          t.tagName === 'TEXTAREA' ||
          t.tagName === 'SELECT'
        ) {
          return;
        }
      }
      if (disabled) return;
      e.preventDefault();
      inputRef.current?.focus();
    }
    window.addEventListener('keydown', onWindowKeyDown);
    return () => window.removeEventListener('keydown', onWindowKeyDown);
  }, [disabled]);

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      inputRef.current?.blur();
      return;
    }
    if (e.key !== 'Enter') return;
    if (sending || disabled) return;
    const result = validateChatText(value);
    if (!result.ok) {
      setError(REASON_MESSAGES[result.reason] ?? '');
      return;
    }
    setError('');
    setSending(true);
    const sentText = result.text;
    setValue('');
    chatInParty(slug, principal, sentText)
      .catch((err: unknown) => {
        setError(describeChatError(err));
        setValue(sentText);
      })
      .finally(() => {
        setSending(false);
      });
  }

  return (
    <div
      onClick={(e) => e.stopPropagation()}
      onPointerDown={(e) => e.stopPropagation()}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        margin: '12px auto 0',
        width: '100%',
      }}
    >
      <input
        ref={inputRef}
        type="text"
        value={value}
        disabled={disabled || sending}
        title={disabled ? 'Reconnecting…' : undefined}
        placeholder={
          disabled ? 'Reconnecting…' : 'Say something… (press T to chat, Esc to exit)'
        }
        maxLength={CHAT_MAX_LEN}
        onChange={(e) => {
          setValue(e.target.value);
          if (error) setError('');
        }}
        onKeyDown={onKeyDown}
        style={{
          width: '100%',
          padding: '10px 16px',
          fontFamily: 'var(--op-font-display)',
          fontWeight: 600,
          fontSize: 14,
          borderRadius: 999,
          border: '3px solid var(--op-ink)',
          background: disabled ? 'var(--op-paper-2)' : '#fff',
          color: 'var(--op-ink)',
          outline: 'none',
          boxShadow: '3px 3px 0 var(--op-shadow)',
        }}
      />
      {error && (
        <div
          role="alert"
          style={{
            fontFamily: 'var(--op-font-mono)',
            fontSize: 12,
            fontWeight: 700,
            color: 'var(--op-ink)',
            background: 'var(--op-coral)',
            border: '2px solid var(--op-ink)',
            padding: '2px 8px',
            borderRadius: 8,
            alignSelf: 'flex-start',
          }}
        >
          {error}
        </div>
      )}
      {value.length > 0 && (
        <div
          aria-live="polite"
          style={{
            fontFamily: 'var(--op-font-mono)',
            fontSize: 11,
            fontWeight: 700,
            color: value.length >= CHAT_MAX_LEN - 10 ? 'var(--op-coral)' : 'var(--op-muted)',
            background: 'var(--op-paper)',
            border: '2px solid var(--op-ink)',
            padding: '1px 8px',
            borderRadius: 6,
            alignSelf: 'flex-end',
          }}
        >
          {value.length}/{CHAT_MAX_LEN}
        </div>
      )}
    </div>
  );
}
