import { useEffect, useRef, useState } from 'react';
import type {
  ChatEvent,
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
import { RadialReactionPicker } from './RadialReactionPicker';
import { Module, isInZone } from './modules/Module';
import { ModuleModal } from './modules/ModuleModal';

const SPEED = 220; // logical units / sec

type ObserveResponse = {
  modules?: ModuleSnapshot[];
  lighting?: LightingPreset;
  active_reactions?: { actor_id: string; emoji: string; expires_at: number }[];
  recent_chat?: ChatEvent[];
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

type PlacedModule = Extract<ModuleSnapshot, { kind: 'stickynotes' | 'drawboard' }>;

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
  const [openModuleId, setOpenModuleId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const inputBlocked = pickerOpen || openModuleId !== null;
  const { position, setTarget } = useMovement({
    worldWidth: width,
    worldHeight: height,
    speed: SPEED,
    walls: party.room.walls,
    onMove,
    moveThrottleMs: 100,
    paused: inputBlocked,
  });
  const floorRef = useRef<HTMLDivElement>(null);

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
    if (inputBlocked) return;
    const rect = floorRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    const logicalX = ((e.clientX - rect.left) / rect.width) * width;
    const logicalY = ((e.clientY - rect.top) / rect.height) * height;
    setTarget({ x: logicalX, y: logicalY });
  }

  const myPosition = { x: position.x, y: position.y };

  // r opens the radial reaction picker (picker owns its own r/Esc to close);
  // e opens the nearest in-range module; Esc closes an open module.
  useEffect(() => {
    if (!principal) return;
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      const k = e.key.toLowerCase();
      if (k === 'r') {
        if (openModuleId || pickerOpen) return;
        e.preventDefault();
        setPickerOpen(true);
        return;
      }
      if (k === 'escape') {
        if (pickerOpen) return; // picker handles its own Escape
        if (openModuleId) setOpenModuleId(null);
        return;
      }
      if (k === 'e') {
        if (pickerOpen || openModuleId || !modules) return;
        for (const m of modules) {
          if (m.kind === 'stickynotes' || m.kind === 'drawboard') {
            if (isInZone(m, myPosition)) {
              e.preventDefault();
              setOpenModuleId(m.id);
              return;
            }
          }
        }
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [principal, modules, myPosition, openModuleId, pickerOpen]);

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

  const placedModules = (modules ?? []).filter(
    (m): m is PlacedModule => m.kind === 'stickynotes' || m.kind === 'drawboard',
  );
  const openModule = openModuleId
    ? placedModules.find((m) => m.id === openModuleId) ?? null
    : null;

  // Reactions picker is anchored to the local avatar. Convert world coords
  // (0..width / 0..height) to percent of the floor for absolute positioning.
  const anchorPercent = {
    x: (position.x / width) * 100,
    y: (position.y / height) * 100,
  };

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
        {placedModules.map((m) => (
          <Module
            key={m.id}
            mod={m}
            myPosition={myPosition}
            onOpen={(id) => setOpenModuleId(id)}
            worldWidth={width}
            worldHeight={height}
          />
        ))}
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
          <ReactionLayer
            reactions={reactions}
            participants={renderList}
            worldWidth={width}
            worldHeight={height}
          />
        ) : null}
        {lighting ? <LightingOverlay preset={lighting} /> : null}
        <MusicPill label={party.music.label} />
        {principal ? (
          <RadialReactionPicker
            open={pickerOpen && realtimeStatus !== 'closed'}
            anchorPercent={anchorPercent}
            onPick={(emoji) => {
              void react(party.slug, principal, emoji);
            }}
            onClose={() => setPickerOpen(false)}
          />
        ) : null}
      </div>
      {principal ? (
        <div
          aria-live="polite"
          style={{
            margin: '8px auto 0',
            textAlign: 'center',
            fontSize: 12,
            color: '#555',
            letterSpacing: 0.4,
          }}
        >
          press <kbd>R</kbd> to react · walk near a board and press <kbd>E</kbd> to interact
        </div>
      ) : null}
      {openModule && principal ? (
        <ModuleModal
          mod={openModule}
          principal={principal}
          slug={party.slug}
          inZone={isInZone(openModule, myPosition)}
          onClose={() => setOpenModuleId(null)}
        />
      ) : null}
    </div>
  );
}
