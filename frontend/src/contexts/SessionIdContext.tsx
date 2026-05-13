import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

export const SESSION_ID_KEY = 'session_id';

type SessionIdContextValue = {
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
};

const SessionIdContext = createContext<SessionIdContextValue | null>(null);

export function SessionIdProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionIdState] = useState<string | null>(
    () => localStorage.getItem(SESSION_ID_KEY),
  );
  const setSessionId = useCallback((id: string | null) => {
    if (id == null) localStorage.removeItem(SESSION_ID_KEY);
    else localStorage.setItem(SESSION_ID_KEY, id);
    setSessionIdState(id);
  }, []);

  return (
    <SessionIdContext.Provider value={{ sessionId, setSessionId }}>
      {children}
    </SessionIdContext.Provider>
  );
}

export function useSessionId(): SessionIdContextValue {
  const ctx = useContext(SessionIdContext);
  if (ctx == null) {
    throw new Error('useSessionId must be used inside <SessionIdProvider>');
  }
  return ctx;
}
