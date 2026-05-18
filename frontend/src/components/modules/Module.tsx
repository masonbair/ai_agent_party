import type { ModuleSnapshot } from '../../api/types';
import type { Principal } from '../../api/party';
import { StickyWall } from './StickyWall';
import { DrawBoard } from './DrawBoard';

type Props = {
  mod: ModuleSnapshot;
  principal: Principal;
  slug: string;
  myPosition: { x: number; y: number } | null;
};

function isInZone(
  mod: ModuleSnapshot,
  pos: { x: number; y: number } | null,
): boolean {
  if (!pos) return false;
  const r = mod.interactionRect;
  return (
    pos.x >= r.x && pos.x <= r.x + r.w && pos.y >= r.y && pos.y <= r.y + r.h
  );
}

export function Module({ mod, principal, slug, myPosition }: Props) {
  const inZone = isInZone(mod, myPosition);
  if (mod.kind === 'stickynotes') {
    return (
      <StickyWall mod={mod} principal={principal} slug={slug} inZone={inZone} />
    );
  }
  if (mod.kind === 'drawboard') {
    return (
      <DrawBoard mod={mod} principal={principal} slug={slug} inZone={inZone} />
    );
  }
  return null;
}
