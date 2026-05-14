import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSessionId } from '../contexts/SessionIdContext';
import { useSessionPresence } from '../hooks/useSessionPresence';

export default function SessionPresenceManager() {
  const { sessionId, setSessionId } = useSessionId();
  const navigate = useNavigate();

  const onEvicted = useCallback(() => {
    setSessionId(null);
    navigate('/?takeover=1', { replace: true });
  }, [navigate, setSessionId]);

  useSessionPresence({ sessionId, onEvicted });
  return null;
}
