import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiGet } from '../api/client';
import { principalKey, threadKey } from '../api/dm';
import type { User } from '../api/types';
import { DmProvider } from '../contexts/DmContext';
import { useSessionId } from '../contexts/SessionIdContext';
import { useInbox } from '../hooks/useInbox';
import DmDrawer from './DmDrawer';
import InboxButton from './InboxButton';

const TOAST_TIMEOUT_MS = 4200;

function isEditingTarget(t: EventTarget | null): boolean {
  if (!t || !(t instanceof HTMLElement)) return false;
  if (t.isContentEditable) return true;
  const tag = t.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

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

  const inbox = useInbox({ principal, onEvicted, drawerOpen });

  // Esc closes the drawer (or backs out of an open thread first).
  useEffect(() => {
    if (!drawerOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Escape') return;
      e.stopPropagation();
      if (inbox.openedKey) {
        inbox.closeThread();
      } else {
        setDrawerOpen(false);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawerOpen, inbox.openedKey, inbox.closeThread]);

  // "i" toggles the inbox drawer when nothing else is focused.
  useEffect(() => {
    if (!principal) return;
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'i' && e.key !== 'I') return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isEditingTarget(e.target)) return;
      e.preventDefault();
      setDrawerOpen((v) => !v);
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [principal]);

  // When the drawer closes, drop focus off the (now-hidden) composer / buttons
  // so WASD keydown reaches the window listener and the avatar can move again.
  const wasOpenRef = useRef(false);
  useEffect(() => {
    if (wasOpenRef.current && !drawerOpen) {
      const el = document.activeElement;
      if (el instanceof HTMLElement) el.blur();
    }
    wasOpenRef.current = drawerOpen;
  }, [drawerOpen]);

  // Auto-dismiss the incoming-DM toast.
  useEffect(() => {
    if (!inbox.latestIncoming) return;
    const id = window.setTimeout(
      () => inbox.clearLatestIncoming(),
      TOAST_TIMEOUT_MS,
    );
    return () => window.clearTimeout(id);
  }, [inbox.latestIncoming, inbox.clearLatestIncoming]);

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

  const toast = inbox.latestIncoming;
  const toastVisible = !!toast && !drawerOpen;

  return (
    <DmProvider value={{ openDmWith }}>
      {principal ? (
        <div
          style={{
            position: 'fixed',
            bottom: 16,
            right: 16,
            zIndex: 50,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'flex-end',
            gap: 10,
          }}
        >
          {toastVisible && toast ? (
            <button
              type="button"
              key={toast.key}
              onClick={async () => {
                inbox.clearLatestIncoming();
                setDrawerOpen(true);
                await inbox.openThread(toast.thread_key);
              }}
              aria-label={`New message from ${toast.sender_name}`}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                background: 'white',
                border: '1px solid rgba(0,0,0,0.08)',
                borderRadius: 999,
                padding: '6px 12px 6px 6px',
                boxShadow: '0 6px 18px rgba(0,0,0,0.12)',
                cursor: 'pointer',
                animation: 'dm-toast-in 180ms ease-out',
                maxWidth: 260,
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  background: toast.sender_color ?? '#999',
                  border: '2px solid white',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.15)',
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 13,
                  lineHeight: 1.25,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  minWidth: 0,
                }}
              >
                <strong>{toast.sender_name}</strong>
                <span style={{ color: '#666' }}> {toast.text}</span>
              </span>
            </button>
          ) : null}
          <InboxButton
            unreadCount={inbox.totalUnread}
            onClick={() => setDrawerOpen((v) => !v)}
          />
        </div>
      ) : null}
      <style>{`@keyframes dm-toast-in {
        from { opacity: 0; transform: translateX(8px); }
        to { opacity: 1; transform: translateX(0); }
      }`}</style>
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
