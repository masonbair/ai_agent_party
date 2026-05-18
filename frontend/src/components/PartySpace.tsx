import { useEffect, useRef } from 'react';
import type {
  LightingPreset,
  ModuleSnapshot,
  Participant,
  PartyConfig,
  User,
} from '../api/types';
import type { Principal } from '../api/party';
import { useMovement } from '../hooks/useMovement';
import { apiGet } from '../api/client';
import { react } from '../api/modules';
import Avatar from './Avatar';
import MusicPill from './MusicPill';
import Wall from './Wall';
import Zone from './Zone';
import { LightingOverlay } from './LightingOverlay';
import { ReactionLayer } from './ReactionLayer';
import { ReactionPalette } from './ReactionPalette';
import { Module } from './modules/Module';

const SPEED = 220; // logical units / sec

type ObserveResponse = {
  modules?: ModuleSnapshot[];
  lighting?: LightingPreset;
  active_reactions?: { actor_id: string; emoji: string; expires_at: number }[];
};

type ApplyObserveInitial = (payload: {
  modules: ModuleSnapshot[];
  lighting: LightingPreset;
  active_reactions: { actor_id: string; emoji: string; expires_at: number }[];
}) => void;

type Props = {
  party: PartyConfig;
  user: User;
  participants?: Participant[];
  onMove?: (x: number, y: number) => void;
  principal?: Principal;
  modules?: ModuleSnapshot[];
  lighting?: LightingPreset;
  reactions?: Map<string, { emoji: string; expiresAt: number }>;
  applyObserveInitial?: ApplyObserveInitial;
  realtimeStatus?: 'connecting' | 'open' | 'closed';
};

export default function PartySpace({
  party,
  user,
  participants,
  onMove,
  principal,
  modules,
  lighting,
  reactions,
  applyObserveInitial,
  realtimeStatus,
}: Props) {
  const { width, height } = party.worldSize;
  const { position, setTarget } = useMovement({
    worldWidth: width,
    worldHeight: height,
    speed: SPEED,
    walls: party.room.walls,
    onMove,
    moveThrottleMs: 100,
  });
  const floorRef = useRef<HTMLDivElement>(null);

  // Seed initial state (modules, lighting, active reactions) via /observe.
  useEffect(() => {
    if (!applyObserveInitial) return;
    let cancelled = false;
    apiGet<ObserveResponse>(`/api/parties/${party.slug}/observe`)
      .then((r) => {
        if (cancelled) return;
        applyObserveInitial({
          modules: r.modules ?? [],
          lighting: r.lighting ?? 'day',
          active_reactions: r.active_reactions ?? [],
        });
      })
      .catch(() => {
        /* observe is best-effort for module seeding */
      });
    return () => {
      cancelled = true;
    };
  }, [party.slug, applyObserveInitial]);

  function onClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = floorRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    const logicalX = ((e.clientX - rect.left) / rect.width) * width;
    const logicalY = ((e.clientY - rect.top) / rect.height) * height;
    setTarget({ x: logicalX, y: logicalY });
  }

  // If participants is provided and non-empty, render everyone (overriding the
  // local-only view). The local user's x/y is overridden with the hook's
  // `position` so the local avatar stays visually responsive even before the
  // server echoes a move. Otherwise fall back to the single-player path:
  // render only the local user.
  const renderList: Participant[] =
    participants && participants.length > 0
      ? participants.map((p) =>
          p.id === user.session_id ? { ...p, x: position.x, y: position.y } : p,
        )
      : [
          {
            id: user.session_id,
            kind: 'human' as const,
            username: user.username,
            color: user.color,
            x: position.x,
            y: position.y,
          },
        ];

  const myPosition = { x: position.x, y: position.y };

  return (
    <div
      style={{
        width: 'min(95vw, 1000px)',
        aspectRatio: `${width} / ${height}`,
        margin: '24px auto',
        position: 'relative',
      }}
    >
      <div
        ref={floorRef}
        onClick={onClick}
        style={{
          position: 'absolute',
          inset: 0,
          background: party.theme.floor,
          border: party.room.border,
          borderRadius: party.room.borderRadius ?? 0,
          clipPath: party.room.clipPath ?? 'none',
          overflow: 'hidden',
          boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
      >
        {party.zones.map((z) => (
          <Zone key={z.id} zone={z} />
        ))}
        {party.room.walls.map((w, i) => (
          <Wall key={i} wall={w} />
        ))}
        {modules && principal
          ? modules.map((m) => (
              <Module
                key={m.id}
                mod={m}
                principal={principal}
                slug={party.slug}
                myPosition={myPosition}
              />
            ))
          : null}
        {renderList.map((p) => (
          <Avatar
            key={p.id}
            username={p.username}
            color={p.color}
            x={p.x}
            y={p.y}
            worldWidth={width}
            worldHeight={height}
            variant={p.id === user.session_id ? 'self' : 'other'}
          />
        ))}
        {reactions ? (
          <ReactionLayer reactions={reactions} participants={renderList} />
        ) : null}
        {lighting ? <LightingOverlay preset={lighting} /> : null}
        <MusicPill label={party.music.label} />
      </div>
      {principal ? (
        <ReactionPalette
          disabled={realtimeStatus !== undefined && realtimeStatus !== 'open'}
          onSelect={(emoji) => {
            void react(party.slug, principal, emoji);
          }}
        />
      ) : null}
    </div>
  );
}
