import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import { useSessionId } from '../contexts/SessionIdContext';
import type { User } from '../api/types';

const STORAGE_KEY = 'session_id';

export function getStoredSessionId(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setStoredSessionId(id: string): void {
  localStorage.setItem(STORAGE_KEY, id);
}

export function clearStoredSessionId(): void {
  localStorage.removeItem(STORAGE_KEY);
}

type State =
  | { status: 'loading' }
  | { status: 'authed'; user: User }
  | { status: 'anon' };

export function useSession(): State {
  const { sessionId, setSessionId } = useSessionId();
  const [state, setState] = useState<State>({ status: 'loading' });
  const navigate = useNavigate();

  useEffect(() => {
    if (!sessionId) {
      setState({ status: 'anon' });
      navigate('/', { replace: true });
      return;
    }
    setState({ status: 'loading' });
    apiGet<User>(`/api/session/${sessionId}`)
      .then((user) => setState({ status: 'authed', user }))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setSessionId(null);
        }
        setState({ status: 'anon' });
        navigate('/', { replace: true });
      });
  }, [sessionId, navigate, setSessionId]);

  return state;
}
