import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Principal } from '../api/party';
import {
  type DmMessage,
  type ThreadSummary,
  getThreadHistory,
  listThreads,
  principalKey,
  sendDm,
} from '../api/dm';

type Status = 'connecting' | 'open' | 'closed';

type Options = {
  principal: Principal | null;
  onEvicted?: () => void;
};

function lastReadKey(thread_key: string): string {
  return `openparty.dm.lastRead.${thread_key}`;
}

function readLastRead(thread_key: string): number {
  try {
    const raw = localStorage.getItem(lastReadKey(thread_key));
    return raw ? Number(raw) || 0 : 0;
  } catch {
    return 0;
  }
}

function writeLastRead(thread_key: string, message_id: number) {
  try {
    localStorage.setItem(lastReadKey(thread_key), String(message_id));
  } catch {
    /* ignore quota */
  }
}

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/inbox`;
}

export type OpenedThread = {
  messages: DmMessage[];
  loadOlder: () => Promise<void>;
  sendError: string | null;
  send: (text: string) => Promise<void>;
  canSend: boolean;
};

export function useInbox({ principal, onEvicted }: Options) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [status, setStatus] = useState<Status>('connecting');
  const [openedKey, setOpenedKey] = useState<string | null>(null);
  const [messagesByThread, setMessagesByThread] = useState<
    Record<string, DmMessage[]>
  >({});
  const [unreadVersion, setUnreadVersion] = useState(0);
  const [sendErrors, setSendErrors] = useState<Record<string, string | null>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const evictedRef = useRef(false);

  useEffect(() => {
    if (!principal) return;
    let cancelled = false;
    let reconnect: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled || !principal) return;
      setStatus('connecting');
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;
      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', principal }));
        setStatus('open');
      };
      ws.onmessage = (e: MessageEvent) => {
        let frame: unknown;
        try {
          frame = JSON.parse(typeof e.data === 'string' ? e.data : '');
        } catch {
          return;
        }
        if (!frame || typeof frame !== 'object') return;
        const f = frame as { type?: string };
        if (f.type === 'evicted') {
          evictedRef.current = true;
          onEvicted?.();
          ws.close();
          return;
        }
        if (f.type === 'dm') {
          const dm = frame as {
            thread_key: string;
            message: DmMessage;
          };
          ingestMessage(dm.thread_key, dm.message);
        }
      };
      ws.onclose = () => {
        setStatus('closed');
        if (cancelled || evictedRef.current) return;
        reconnect = setTimeout(connect, 1000);
      };
      ws.onerror = () => {};
    }

    // Initial HTTP fetch of threads
    listThreads(principal)
      .then((r) => {
        if (!cancelled) setThreads(r.threads);
      })
      .catch(() => {});
    connect();
    return () => {
      cancelled = true;
      if (reconnect) clearTimeout(reconnect);
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [principal?.id, principal?.kind]);

  const ingestMessage = useCallback(
    (thread_key: string, message: DmMessage) => {
      setMessagesByThread((prev) => {
        const existing = prev[thread_key] ?? [];
        if (existing.some((m) => m.id === message.id)) return prev;
        return { ...prev, [thread_key]: [...existing, message] };
      });
      setThreads((prev) => {
        const idx = prev.findIndex((t) => t.thread_key === thread_key);
        const meKey = principal ? principalKey(principal) : '';
        const otherKey = thread_key
          .split('|')
          .find((k) => k !== meKey) ?? thread_key;
        const updated: ThreadSummary =
          idx >= 0
            ? {
                ...prev[idx],
                last_at: message.at,
                last_text: message.text,
                last_sender_kind: message.sender_kind,
                last_sender_id: message.sender_id,
                last_sender_name: message.sender_name,
                last_message_id: message.id,
              }
            : {
                thread_key,
                other_principal_key: otherKey,
                last_at: message.at,
                last_text: message.text,
                last_sender_kind: message.sender_kind,
                last_sender_id: message.sender_id,
                last_sender_name: message.sender_name,
                last_message_id: message.id,
              };
        const rest = idx >= 0 ? prev.filter((_, i) => i !== idx) : prev;
        const next = [updated, ...rest];
        next.sort((a, b) => b.last_at - a.last_at);
        return next;
      });
    },
    [principal],
  );

  const unreadCount = useCallback(
    (thread_key: string): number => {
      void unreadVersion; // re-read localStorage on bumps
      const lastRead = readLastRead(thread_key);
      const msgs = messagesByThread[thread_key] ?? [];
      const fromMsgs = msgs.filter((m) => m.id > lastRead).length;
      if (fromMsgs > 0) return fromMsgs;
      const summary = threads.find((t) => t.thread_key === thread_key);
      if (summary && summary.last_message_id > lastRead) return 1;
      return 0;
    },
    [messagesByThread, threads, unreadVersion],
  );

  const totalUnread = useMemo(() => {
    return threads.reduce((sum, t) => sum + unreadCount(t.thread_key), 0);
  }, [threads, unreadCount]);

  const markRead = useCallback(
    (thread_key: string) => {
      const summary = threads.find((t) => t.thread_key === thread_key);
      const msgs = messagesByThread[thread_key] ?? [];
      const maxIdSummary = summary?.last_message_id ?? 0;
      const maxIdMsgs = msgs.reduce((m, x) => Math.max(m, x.id), 0);
      const top = Math.max(maxIdSummary, maxIdMsgs);
      if (top > 0) writeLastRead(thread_key, top);
      setUnreadVersion((v) => v + 1);
    },
    [threads, messagesByThread],
  );

  const loadOlder = useCallback(
    async (thread_key: string) => {
      if (!principal) return;
      const existing = messagesByThread[thread_key] ?? [];
      const beforeId =
        existing.length > 0 ? Math.min(...existing.map((m) => m.id)) : undefined;
      try {
        const r = await getThreadHistory(thread_key, principal, { beforeId });
        const older = r.messages.slice().reverse(); // history is newest-first
        setMessagesByThread((prev) => {
          const existingMsgs = prev[thread_key] ?? [];
          const have = new Set(existingMsgs.map((m) => m.id));
          const merged = [...older.filter((m) => !have.has(m.id)), ...existingMsgs];
          return { ...prev, [thread_key]: merged };
        });
      } catch {
        /* ignore */
      }
    },
    [principal, messagesByThread],
  );

  const openThread = useCallback(
    async (thread_key: string) => {
      setOpenedKey(thread_key);
      if (!messagesByThread[thread_key]) {
        await loadOlder(thread_key);
      }
    },
    [messagesByThread, loadOlder],
  );

  const closeThread = useCallback(() => setOpenedKey(null), []);

  const sendInThread = useCallback(
    async (thread_key: string, otherKey: string, text: string) => {
      if (!principal) return;
      const [kind, id] = otherKey.split(':');
      try {
        await sendDm(principal, { kind: kind as 'human' | 'agent', id }, text);
        setSendErrors((p) => ({ ...p, [thread_key]: null }));
      } catch (err: unknown) {
        const e = err as { body?: { detail?: string } };
        const reason =
          (e?.body?.detail as string | undefined) ?? 'send_failed';
        setSendErrors((p) => ({ ...p, [thread_key]: reason }));
        throw err;
      }
    },
    [principal],
  );

  const sendToPrincipal = useCallback(
    async (recipient: { kind: 'human' | 'agent'; id: string }, text: string) => {
      if (!principal) return;
      try {
        await sendDm(principal, recipient, text);
      } catch (err: unknown) {
        const e = err as { body?: { detail?: string } };
        const reason =
          (e?.body?.detail as string | undefined) ?? 'send_failed';
        const otherKey = principalKey(recipient);
        const myKey = principalKey(principal);
        const tk = [myKey, otherKey].sort().join('|');
        setSendErrors((p) => ({ ...p, [tk]: reason }));
        throw err;
      }
    },
    [principal],
  );

  const openedThread: OpenedThread | null = openedKey
    ? {
        messages: messagesByThread[openedKey] ?? [],
        loadOlder: () => loadOlder(openedKey),
        sendError: sendErrors[openedKey] ?? null,
        canSend: (sendErrors[openedKey] ?? null) === null,
        send: async (text: string) => {
          const summary = threads.find((t) => t.thread_key === openedKey);
          const meKey = principal ? principalKey(principal) : '';
          const otherKey =
            summary?.other_principal_key ??
            openedKey.split('|').find((k) => k !== meKey) ??
            null;
          if (!otherKey) return;
          await sendInThread(openedKey, otherKey, text);
        },
      }
    : null;

  return {
    threads,
    status,
    unreadCount,
    totalUnread,
    markRead,
    openThread,
    closeThread,
    openedKey,
    openedThread,
    sendToPrincipal,
  };
}
