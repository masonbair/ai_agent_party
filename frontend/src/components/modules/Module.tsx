import type { ModuleSnapshot } from '../../api/types';
import { ModuleStructure } from './ModuleStructure';

type Props = {
  mod: ModuleSnapshot;
  myPosition: { x: number; y: number } | null;
  onOpen: (moduleId: string) => void;
};

export function isInZone(
  mod: ModuleSnapshot,
  pos: { x: number; y: number } | null,
): boolean {
  if (mod.kind === 'lighting') return false;
  if (!pos) return false;
  const r = mod.interactionRect;
  return (
    pos.x >= r.x && pos.x <= r.x + r.w && pos.y >= r.y && pos.y <= r.y + r.h
  );
}

// In-world wrapper. Renders the visible structure; clicking it opens the
// full editor modal (managed by PartySpace).
export function Module({ mod, myPosition, onOpen }: Props) {
  if (mod.kind !== 'stickynotes' && mod.kind !== 'drawboard') return null;
  const inZone = isInZone(mod, myPosition);
  return (
    <ModuleStructure mod={mod} inZone={inZone} onOpen={() => onOpen(mod.id)} />
  );
}
