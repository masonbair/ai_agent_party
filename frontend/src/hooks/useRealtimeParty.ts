import { useEffect, useRef, useState } from 'react';
import type { Participant } from '../api/types';
import type { Principal } from '../api/party';

type Options = {
  slug: string;
  principal: Principal;
  onEvicted?: () => void;
};

type Status = 'connecting' | 'open' | 'closed';

function wsUrlFor(slug: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/parties/${slug}/ws`;
}

export function useRealtimeParty({ slug, principal, onEvicted }: Options) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [status, setStatus] = useState<Status>('connecting');
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const evictedRef = useRef(false);

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
          } else if (ev.type === 'move') {
            const m = ev as unknown as { participant_id: string; x: number; y: number };
            if (m.participant_id === principal.id) return; // ignore self-echo
            setParticipants((prev) =>
              prev.map((q) =>
                q.id === m.participant_id ? { ...q, x: m.x, y: m.y } : q,
              ),
            );
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

      ws.onerror = () => {
        // onclose handler will run next; no extra cleanup here.
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer != null) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [slug, principal.id, principal.kind]);

  return { participants, status };
}
