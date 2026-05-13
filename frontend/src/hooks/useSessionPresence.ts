import { useEffect, useRef } from 'react';

type Options = {
  sessionId: string | null;
  onEvicted?: () => void;
};

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/session/ws`;
}

export function useSessionPresence({ sessionId, onEvicted }: Options): void {
  const evictedRef = useRef(false);

  useEffect(() => {
    if (!sessionId) return;
    evictedRef.current = false;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let backoff = 1000;
    let ws: WebSocket | null = null;

    function connect() {
      if (cancelled) return;
      ws = new WebSocket(wsUrl());

      ws.onopen = () => {
        ws?.send(JSON.stringify({ type: 'auth', session_id: sessionId }));
        backoff = 1000;
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
          ws?.close();
          return;
        }
      };

      ws.onclose = () => {
        if (cancelled || evictedRef.current) return;
        const delay = Math.min(backoff, 8000);
        backoff = Math.min(backoff * 2, 8000);
        reconnectTimer = setTimeout(connect, delay);
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer != null) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [sessionId, onEvicted]);
}
