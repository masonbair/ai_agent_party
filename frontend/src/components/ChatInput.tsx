// frontend/src/components/ChatInput.tsx
import { useEffect, useRef, useState } from 'react';
import { chatInParty, type Principal } from '../api/party';
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
      .catch(() => {
        setError('Failed to send');
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
        position: 'absolute',
        left: 12,
        right: 12,
        bottom: 12,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        zIndex: 10,
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
          padding: '8px 12px',
          fontSize: 14,
          borderRadius: 999,
          border: '1px solid #c9b58a',
          background: disabled ? '#eee' : '#fff',
          outline: 'none',
          boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
        }}
      />
      {error && (
        <div
          role="alert"
          style={{
            fontSize: 12,
            color: '#b03030',
            background: 'rgba(255,255,255,0.9)',
            padding: '2px 8px',
            borderRadius: 6,
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
            fontSize: 11,
            color: value.length >= CHAT_MAX_LEN - 20 ? '#b86b00' : '#6a6a6a',
            background: 'rgba(255,255,255,0.85)',
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
