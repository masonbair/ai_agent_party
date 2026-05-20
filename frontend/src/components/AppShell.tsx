import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import { principalKey, threadKey } from '../api/dm';
import type { User } from '../api/types';
import { DmProvider } from '../contexts/DmContext';
import { useSessionId } from '../contexts/SessionIdContext';
import { useInbox } from '../hooks/useInbox';
import DmDrawer from './DmDrawer';
import InboxButton from './InboxButton';

export default function AppShell({ children }: { children: ReactNode }) {
  const { sessionId, setSessionId } = useSessionId();
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [displayNames, setDisplayNames] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!sessionId) {
      setUser(null);
      return;
    }
    apiGet<User>(`/api/session/${sessionId}`)
      .then(setUser)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setSessionId(null);
        }
        setUser(null);
      });
  }, [sessionId, setSessionId]);

  const principal = useMemo(
    () => (user ? { kind: 'human' as const, id: user.session_id } : null),
    [user],
  );

  const onEvicted = useCallback(() => {
    setSessionId(null);
    navigate('/?takeover=1', { replace: true });
  }, [setSessionId, navigate]);

  const inbox = useInbox({ principal, onEvicted });

  const openDmWith = useCallback(
    async (
      recipient: { kind: 'human' | 'agent'; id: string },
      displayName?: string,
    ) => {
      if (!principal) return;
      const me = principalKey(principal);
      const other = principalKey(recipient);
      if (me === other) return;
      const tk = threadKey(me, other);
      if (displayName) {
        setDisplayNames((prev) =>
          prev[tk] === displayName ? prev : { ...prev, [tk]: displayName },
        );
      }
      setDrawerOpen(true);
      await inbox.openThread(tk);
    },
    [principal, inbox],
  );

  return (
    <DmProvider value={{ openDmWith }}>
      {principal ? (
        <div
          style={{
            position: 'fixed',
            top: 12,
            right: 12,
            zIndex: 50,
          }}
        >
          <InboxButton
            unreadCount={inbox.totalUnread}
            onClick={() => setDrawerOpen((v) => !v)}
          />
        </div>
      ) : null}
      {children}
      <DmDrawer
        open={drawerOpen && !!principal}
        onClose={() => setDrawerOpen(false)}
        principal={principal}
        threads={inbox.threads}
        unreadCount={inbox.unreadCount}
        openedKey={inbox.openedKey}
        openedThread={inbox.openedThread}
        onOpenThread={inbox.openThread}
        onCloseThread={inbox.closeThread}
        onMarkRead={inbox.markRead}
        displayNames={displayNames}
      />
    </DmProvider>
  );
}
