import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import { useSessionId } from '../contexts/SessionIdContext';
import type { User } from '../api/types';

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
