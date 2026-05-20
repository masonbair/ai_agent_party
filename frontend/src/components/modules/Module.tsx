import type { ModuleSnapshot } from '../../api/types';
import { ModuleStructure } from './ModuleStructure';

type Props = {
  mod: ModuleSnapshot;
  myPosition: { x: number; y: number } | null;
  onOpen: (moduleId: string) => void;
  worldWidth?: number;
  worldHeight?: number;
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

export function Module({ mod, myPosition, onOpen, worldWidth, worldHeight }: Props) {
  if (mod.kind !== 'stickynotes' && mod.kind !== 'drawboard') return null;
  const inZone = isInZone(mod, myPosition);
  return (
    <ModuleStructure
      mod={mod}
      inZone={inZone}
      onOpen={() => onOpen(mod.id)}
      worldWidth={worldWidth}
      worldHeight={worldHeight}
    />
  );
}
