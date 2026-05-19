import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  LightingPreset,
  ModuleSnapshot,
  Participant,
  StickyNote,
  Stroke,
} from '../api/types';
import type { Principal } from '../api/party';

type Options = {
  slug: string;
  principal: Principal;
  onEvicted?: () => void;
};

type Status = 'connecting' | 'open' | 'closed';

type ReactionState = { emoji: string; expiresAt: number };

type ObservePayload = {
  modules: ModuleSnapshot[];
  lighting: LightingPreset;
  active_reactions: { actor_id: string; emoji: string; expires_at: number }[];
};

function wsUrlFor(slug: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/parties/${slug}/ws`;
}

export function useRealtimeParty({ slug, principal, onEvicted }: Options) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [status, setStatus] = useState<Status>('connecting');
  const [reactions, setReactions] = useState<Map<string, ReactionState>>(
    new Map(),
  );
  const [lighting, setLighting] = useState<LightingPreset>('day');
  const [modules, setModules] = useState<ModuleSnapshot[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const evictedRef = useRef(false);

  const applyObserveInitial = useCallback((payload: ObservePayload) => {
    setModules(payload.modules ?? []);
    if (payload.lighting) setLighting(payload.lighting);
    const m = new Map<string, ReactionState>();
    for (const r of payload.active_reactions ?? []) {
      m.set(r.actor_id, { emoji: r.emoji, expiresAt: r.expires_at * 1000 });
    }
    setReactions(m);
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
          } else if (ev.type === 'move') {
            const m = ev as unknown as {
              participant_id: string;
              x: number;
              y: number;
            };
            if (m.participant_id === principal.id) return; // ignore self-echo
            setParticipants((prev) =>
              prev.map((q) =>
                q.id === m.participant_id ? { ...q, x: m.x, y: m.y } : q,
              ),
            );
          } else if (ev.type === 'reaction') {
            const r = ev as unknown as {
              actor_id: string;
              emoji: string;
              expires_at: number;
            };
            const expiresAt = r.expires_at * 1000;
            setReactions((prev) => {
              const next = new Map(prev);
              next.set(r.actor_id, { emoji: r.emoji, expiresAt });
              return next;
            });
            setTimeout(
              () => {
                setReactions((prev) => {
                  if (prev.get(r.actor_id)?.expiresAt !== expiresAt) return prev;
                  const next = new Map(prev);
                  next.delete(r.actor_id);
                  return next;
                });
              },
              Math.max(0, expiresAt - Date.now()),
            );
          } else if (ev.type === 'lighting_changed') {
            const p = (ev as unknown as { preset: LightingPreset }).preset;
            setLighting(p);
          } else if (
            ev.type === 'note_created' ||
            ev.type === 'note_updated'
          ) {
            const e2 = ev as unknown as {
              type: string;
              module_id: string;
              note: StickyNote;
            };
            setModules((prev) =>
              prev.map((m) => {
                if (m.id !== e2.module_id || m.kind !== 'stickynotes') return m;
                if (e2.type === 'note_created') {
                  if (m.notes.some((n) => n.id === e2.note.id)) return m;
                  return { ...m, notes: [...m.notes, e2.note] };
                }
                return {
                  ...m,
                  notes: m.notes.map((n) =>
                    n.id === e2.note.id ? e2.note : n,
                  ),
                };
              }),
            );
          } else if (ev.type === 'note_deleted') {
            const e2 = ev as unknown as {
              module_id: string;
              note_id: string;
            };
            setModules((prev) =>
              prev.map((m) =>
                m.id === e2.module_id && m.kind === 'stickynotes'
                  ? { ...m, notes: m.notes.filter((n) => n.id !== e2.note_id) }
                  : m,
              ),
            );
          } else if (ev.type === 'stroke_added') {
            const e2 = ev as unknown as { module_id: string; stroke: Stroke };
            setModules((prev) =>
              prev.map((m) =>
                m.id === e2.module_id && m.kind === 'drawboard'
                  ? { ...m, strokes: [...m.strokes, e2.stroke] }
                  : m,
              ),
            );
          } else if (ev.type === 'stroke_dropped') {
            const e2 = ev as unknown as {
              module_id: string;
              stroke_id: string;
            };
            setModules((prev) =>
              prev.map((m) =>
                m.id === e2.module_id && m.kind === 'drawboard'
                  ? {
                      ...m,
                      strokes: m.strokes.filter((s) => s.id !== e2.stroke_id),
                    }
                  : m,
              ),
            );
          } else if (ev.type === 'board_cleared') {
            const e2 = ev as unknown as { module_id: string };
            // Only drop strokes here. The backend emits a vote_changed
            // event right after with the correct tally for the current
            // in-zone population; leave vote state for that to set.
            setModules((prev) =>
              prev.map((m) =>
                m.id === e2.module_id && m.kind === 'drawboard'
                  ? { ...m, strokes: [] }
                  : m,
              ),
            );
          } else if (ev.type === 'vote_changed') {
            const e2 = ev as unknown as {
              module_id: string;
              votes: number;
              needed: number;
            };
            setModules((prev) =>
              prev.map((m) =>
                m.id === e2.module_id && m.kind === 'drawboard'
                  ? { ...m, vote: { votes: e2.votes, needed: e2.needed } }
                  : m,
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

  return {
    participants,
    status,
    reactions,
    lighting,
    modules,
    applyObserveInitial,
  };
}
