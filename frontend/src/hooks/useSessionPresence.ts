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
  const rejectedRef = useRef(false);
  const onEvictedRef = useRef(onEvicted);
  onEvictedRef.current = onEvicted;

  useEffect(() => {
    if (!sessionId) return;
    rejectedRef.current = false;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let backoff = 1000;
    let ws: WebSocket | null = null;

    function connect() {
      if (cancelled) return;
      ws = new WebSocket(wsUrl());

      ws.onopen = () => {
        // Don't reset backoff on the raw handshake — the server may still
        // reject the auth frame (stale session_id after a backend restart),
        // and resetting here would cause a 1s reconnect storm.
        ws?.send(JSON.stringify({ type: 'auth', session_id: sessionId }));
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
        if (f.type === 'error' || f.type === 'evicted') {
          rejectedRef.current = true;
          onEvictedRef.current?.();
          ws?.close();
          return;
        }
        backoff = 1000;
      };

      ws.onclose = () => {
        if (cancelled || rejectedRef.current) return;
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
  }, [sessionId]);
}
