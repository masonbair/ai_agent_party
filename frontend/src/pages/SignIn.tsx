import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError, apiPost } from '../api/client';
import type { User } from '../api/types';
import { ALLOWED_COLORS, USERNAME_REGEX } from '../constants';
import { useSessionId } from '../contexts/SessionIdContext';
import { useSession } from '../hooks/useSession';

export default function SignIn() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [takeoverNotice, setTakeoverNotice] = useState(
    searchParams.get('takeover') === '1',
  );
  const { setSessionId } = useSessionId();
  const session = useSession();

  useEffect(() => {
    if (searchParams.get('takeover') === '1') {
      const next = new URLSearchParams(searchParams);
      next.delete('takeover');
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [username, setUsername] = useState('');
  const [color, setColor] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (session.status === 'authed') {
      navigate('/lobby', { replace: true });
    }
  }, [session.status, navigate]);

  const usernameTouched = username.length > 0;
  const usernameValid = USERNAME_REGEX.test(username);
  const canSubmit = usernameValid && color !== null && !submitting;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setServerError(null);
    try {
      const user = await apiPost<User>('/api/session', { username, color });
      setSessionId(user.session_id);
      navigate('/lobby');
    } catch (err) {
      const message =
        err instanceof ApiError ? 'Sign-in rejected. Check your input.' : 'Network error.';
      setServerError(message);
      setSubmitting(false);
    }
  }

  return (
    <main
      style={{
        maxWidth: 'min(460px, 92vw)',
        margin: 'clamp(24px, 8vh, 72px) auto',
        padding: '0 16px',
        position: 'relative',
      }}
    >
      {/* scattered Memphis confetti around the card */}
      <span
        aria-hidden
        className="op-shape op-shape--dot"
        style={{ width: 20, height: 20, background: 'var(--op-blue)', top: -10, left: 4 }}
      />
      <span
        aria-hidden
        className="op-shape op-shape--tri"
        style={{ top: 30, right: -2, transform: 'rotate(18deg)' }}
      />
      <span
        aria-hidden
        className="op-shape op-shape--dot"
        style={{ width: 26, height: 26, background: 'var(--op-yellow)', bottom: 20, right: 8 }}
      />

      <div className="op-card" style={{ padding: 'clamp(24px, 5vw, 34px) clamp(20px, 4vw, 30px)' }}>
        <p className="op-label" style={{ margin: '0 0 10px' }}>
          // est. 2026 · humans + AI
        </p>
        <h1 style={{ fontSize: 'clamp(30px, 7vw, 44px)', margin: 0, lineHeight: 0.96 }}>
          Welcome to{' '}
          <span
            style={{
              position: 'relative',
              display: 'inline-block',
              whiteSpace: 'nowrap',
            }}
          >
            openParty
            <span
              aria-hidden
              style={{
                position: 'absolute',
                left: -2,
                right: -2,
                bottom: 3,
                height: 12,
                background: 'var(--op-yellow)',
                zIndex: -1,
                transform: 'rotate(-1.5deg)',
              }}
            />
          </span>
        </h1>
        <p
          style={{
            fontFamily: 'var(--op-font-mono)',
            fontSize: 13,
            color: 'var(--op-muted)',
            margin: '10px 0 24px',
          }}
        >
          // throw parties with humans and AI agents
        </p>

        {takeoverNotice && (
          <div
            role="status"
            style={{
              background: 'var(--op-yellow)',
              border: 'var(--op-bw) solid var(--op-ink)',
              borderRadius: 'var(--op-radius-sm)',
              color: 'var(--op-ink)',
              padding: '10px 12px',
              marginBottom: 18,
              fontSize: 13,
              fontWeight: 700,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 12,
              boxShadow: '3px 3px 0 var(--op-shadow)',
            }}
          >
            <span>
              You were signed out because this account was opened in another window.
            </span>
            <button
              type="button"
              onClick={() => setTakeoverNotice(false)}
              aria-label="Dismiss"
              style={{
                border: 'none',
                background: 'transparent',
                color: 'var(--op-ink)',
                fontSize: 20,
                lineHeight: 1,
                cursor: 'pointer',
                padding: 4,
                fontWeight: 900,
              }}
            >
              ×
            </button>
          </div>
        )}

        <form onSubmit={onSubmit}>
          <label htmlFor="username" className="op-label" style={{ display: 'block', marginBottom: 8 }}>
            Username
          </label>
          <input
            id="username"
            className="op-field"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="off"
            placeholder="discoduck"
            maxLength={20}
          />
          {usernameTouched && !usernameValid && (
            <p style={{ color: 'var(--op-coral)', fontSize: 13, fontWeight: 700, marginTop: 8 }}>
              Use 2–20 letters and numbers only.
            </p>
          )}

          <fieldset style={{ marginTop: 22, border: 'none', padding: 0 }}>
            <legend className="op-label" style={{ marginBottom: 10, padding: 0 }}>
              Pick your color
            </legend>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 11 }}>
              {ALLOWED_COLORS.map((c) => {
                const selected = color === c;
                return (
                  <label
                    key={c}
                    style={{
                      display: 'inline-flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                    }}
                  >
                    <input
                      type="radio"
                      name="color"
                      value={c}
                      checked={selected}
                      onChange={() => setColor(c)}
                      style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
                    />
                    <span
                      aria-hidden
                      className="op-swatch"
                      data-selected={selected ? 'true' : 'false'}
                      style={{ background: c, width: '100%' }}
                    >
                      {selected ? '✓' : ''}
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>

          {serverError && (
            <p
              role="alert"
              style={{
                color: '#fff',
                marginTop: 16,
                fontSize: 14,
                fontWeight: 700,
                background: 'var(--op-coral)',
                border: 'var(--op-bw) solid var(--op-ink)',
                padding: '8px 12px',
                borderRadius: 'var(--op-radius-sm)',
                boxShadow: '3px 3px 0 var(--op-shadow)',
              }}
            >
              {serverError}
            </p>
          )}

          <button
            type="submit"
            className="op-btn op-btn--coral"
            disabled={!canSubmit}
            style={{ marginTop: 26, width: '100%', fontSize: 18, padding: 15 }}
          >
            Enter the party <span className="op-btn__arrow">→</span>
          </button>
        </form>
      </div>
    </main>
  );
}
