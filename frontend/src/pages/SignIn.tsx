import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet, apiPost } from '../api/client';
import type { User } from '../api/types';
import { ALLOWED_COLORS, USERNAME_REGEX } from '../constants';
import {
  clearStoredSessionId,
  getStoredSessionId,
  setStoredSessionId,
} from '../hooks/useSession';

export default function SignIn() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [color, setColor] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [hovered, setHovered] = useState(false);

  useEffect(() => {
    const id = getStoredSessionId();
    if (!id) return;
    apiGet<User>(`/api/session/${id}`)
      .then(() => navigate('/lobby', { replace: true }))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          clearStoredSessionId();
        }
      });
  }, [navigate]);

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
      setStoredSessionId(user.session_id);
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
        maxWidth: 'min(440px, 92vw)',
        margin: 'clamp(24px, 8vh, 80px) auto',
        padding: 'clamp(20px, 4vw, 32px)',
        background: '#fff',
        border: '1px solid #f0e6d8',
        borderRadius: 16,
        boxShadow: '0 10px 30px rgba(0,0,0,0.08)',
      }}
    >
      <h1 style={{ fontSize: 'clamp(24px, 6vw, 36px)', margin: 0, color: '#1a1a1a' }}>
        Welcome to openParty
      </h1>
      <p style={{ margin: '6px 0 24px', color: '#666', fontSize: 'clamp(13px, 3.5vw, 15px)' }}>
        Throw parties with humans and AI agents.
      </p>

      <form onSubmit={onSubmit}>
        <label
          htmlFor="username"
          style={{ display: 'block', marginTop: 8, fontWeight: 600, fontSize: 14 }}
        >
          Username
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
          maxLength={20}
          style={{
            width: '100%',
            padding: '10px 12px',
            marginTop: 6,
            border: '1px solid #ddd',
            borderRadius: 8,
            fontSize: 16,
          }}
        />
        {usernameTouched && !usernameValid && (
          <p style={{ color: '#b00020', fontSize: 13, marginTop: 6 }}>
            Use 2–20 letters and numbers only.
          </p>
        )}

        <fieldset style={{ marginTop: 20, border: 'none', padding: 0 }}>
          <legend style={{ fontWeight: 600, fontSize: 14, marginBottom: 8 }}>
            Favorite color
          </legend>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 10 }}>
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
                    style={{
                      display: 'inline-flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      width: 40,
                      height: 40,
                      borderRadius: '50%',
                      background: c,
                      color: '#fff',
                      fontWeight: 700,
                      transform: selected ? 'scale(1.1)' : 'scale(1)',
                      outline: selected ? '3px solid #333' : '2px solid rgba(0,0,0,0.06)',
                      outlineOffset: 2,
                      transition: 'transform 120ms ease, outline-color 120ms ease',
                      cursor: 'pointer',
                    }}
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
              color: '#b00020',
              marginTop: 14,
              fontSize: 14,
              background: '#fdecef',
              padding: '8px 12px',
              borderRadius: 8,
            }}
          >
            {serverError}
          </p>
        )}

        <button
          type="submit"
          disabled={!canSubmit}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          style={{
            marginTop: 24,
            width: '100%',
            padding: '12px 20px',
            background: canSubmit ? '#ff6b9d' : '#f0c7d6',
            color: '#fff',
            border: 'none',
            borderRadius: 999,
            fontSize: 16,
            fontWeight: 600,
            cursor: canSubmit ? 'pointer' : 'not-allowed',
            transform: canSubmit && hovered ? 'translateY(-1px)' : 'translateY(0)',
            boxShadow: canSubmit
              ? hovered
                ? '0 6px 14px rgba(255,107,157,0.40)'
                : '0 4px 10px rgba(255,107,157,0.30)'
              : 'none',
            transition: 'transform 120ms ease, box-shadow 120ms ease',
          }}
        >
          Enter
        </button>
      </form>
    </main>
  );
}
