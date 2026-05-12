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
        maxWidth: 'min(420px, 92vw)',
        margin: 'clamp(24px, 8vh, 64px) auto',
        padding: 'clamp(16px, 4vw, 24px)',
      }}
    >
      <h1 style={{ fontSize: 'clamp(20px, 5vw, 28px)', margin: 0 }}>
        Welcome to openParty
      </h1>
      <form onSubmit={onSubmit}>
        <label htmlFor="username" style={{ display: 'block', marginTop: 16 }}>
          Username
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="off"
          maxLength={20}
          style={{ width: '100%', padding: 8 }}
        />
        {usernameTouched && !usernameValid && (
          <p style={{ color: '#b00020', fontSize: 14 }}>
            Use 2–20 letters and numbers only.
          </p>
        )}

        <fieldset style={{ marginTop: 16, border: 'none', padding: 0 }}>
          <legend>Favorite color</legend>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 8 }}>
            {ALLOWED_COLORS.map((c) => (
              <label key={c} style={{ display: 'inline-flex' }}>
                <input
                  type="radio"
                  name="color"
                  value={c}
                  checked={color === c}
                  onChange={() => setColor(c)}
                  style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
                />
                <span
                  aria-hidden
                  style={{
                    display: 'block',
                    width: 36,
                    height: 36,
                    borderRadius: '50%',
                    background: c,
                    outline: color === c ? '3px solid #333' : 'none',
                    outlineOffset: 2,
                    cursor: 'pointer',
                  }}
                />
              </label>
            ))}
          </div>
        </fieldset>

        {serverError && (
          <p role="alert" style={{ color: '#b00020' }}>
            {serverError}
          </p>
        )}

        <button type="submit" disabled={!canSubmit} style={{ marginTop: 24, padding: '8px 16px' }}>
          Enter
        </button>
      </form>
    </main>
  );
}
