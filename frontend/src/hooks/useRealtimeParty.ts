// frontend/src/hooks/useRealtimeParty.ts
import { useEffect, useRef, useState } from 'react';
import type { Participant } from '../api/types';
import type { Principal } from '../api/party';

type Options = {
  slug: string;
  principal: Principal;
  onEvicted?: () => void;
};

type Status = 'connecting' | 'open' | 'closed';

export type Bubble = { text: string; expiresAt: number };
export type Bubbles = Record<string, Bubble>;

export const BUBBLE_LIFETIME_MS = 5000;
const BUBBLE_TICK_MS = 250;

function wsUrlFor(slug: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/parties/${slug}/ws`;
}

export function useRealtimeParty({ slug, principal, onEvicted }: Options) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [bubbles, setBubbles] = useState<Bubbles>({});
  const [status, setStatus] = useState<Status>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const evictedRef = useRef(false);

  // Expiry tick: prunes bubbles whose expiresAt has passed.
  useEffect(() => {
    const id = setInterval(() => {
      setBubbles((prev) => {
        const now = Date.now();
        let changed = false;
        const next: Bubbles = {};
        for (const [k, b] of Object.entries(prev)) {
          if (b.expiresAt > now) next[k] = b;
          else changed = true;
        }
        return changed ? next : prev;
      });
    }, BUBBLE_TICK_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!slug || !principal.id) return;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled) return;
      setStatus('connecting');
      const ws = new WebSocket(wsUrlFor(slug));
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'auth', principal }));
        backoffRef.current = 1000;
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
        if (f.type === 'snapshot') {
          const s = frame as { participants: Participant[] };
          setParticipants(s.participants);
        } else if (f.type === 'event') {
          const ev = (frame as { event: { type: string } }).event;
          if (ev.type === 'join') {
            const p = (ev as unknown as { participant: Participant }).participant;
            setParticipants((prev) =>
              prev.some((q) => q.id === p.id) ? prev : [...prev, p],
            );
          } else if (ev.type === 'leave') {
            const id = (ev as unknown as { participant_id: string }).participant_id;
            setParticipants((prev) => prev.filter((q) => q.id !== id));
            setBubbles((prev) => {
              if (!(id in prev)) return prev;
              const next = { ...prev };
              delete next[id];
              return next;
            });
          } else if (ev.type === 'move') {
            const m = ev as unknown as { participant_id: string; x: number; y: number };
            if (m.participant_id === principal.id) return;
            setParticipants((prev) =>
              prev.map((q) =>
                q.id === m.participant_id ? { ...q, x: m.x, y: m.y } : q,
              ),
            );
          } else if (ev.type === 'chat') {
            const c = ev as unknown as { participant_id: string; text: string };
            setBubbles((prev) => ({
              ...prev,
              [c.participant_id]: {
                text: c.text,
                expiresAt: Date.now() + BUBBLE_LIFETIME_MS,
              },
            }));
          }
        }
      };

      ws.onclose = () => {
        setStatus('closed');
        if (cancelled || evictedRef.current) return;
        const delay = Math.min(backoffRef.current, 8000);
        backoffRef.current = Math.min(backoffRef.current * 2, 8000);
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onerror = () => {};
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer != null) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [slug, principal.id, principal.kind]);

  return { participants, status, bubbles };
}
