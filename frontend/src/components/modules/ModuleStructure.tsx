import type { ModuleSnapshot } from '../../api/types';

type Props = {
  mod: Extract<ModuleSnapshot, { kind: 'stickynotes' | 'drawboard' }>;
  inZone: boolean;
  onOpen: () => void;
};

// In-world piece of "furniture". Click or press E (handled in PartySpace) to
// open the full editor in a modal.
export function ModuleStructure({ mod, inZone, onOpen }: Props) {
  const isSticky = mod.kind === 'stickynotes';
  const label = isSticky ? 'NOTE BOARD' : 'WHITE BOARD';
  const accent = isSticky ? '#c89b4a' : '#3a5a8c';
  const surface = isSticky ? '#fbe9a4' : '#fafafa';
  const itemCount =
    mod.kind === 'stickynotes' ? mod.notes.length : mod.strokes.length;

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        if (inZone) onOpen();
      }}
      aria-label={`${label} (${inZone ? 'in range, click or press E' : 'walk closer'})`}
      data-testid={`module-structure-${mod.id}`}
      style={{
        position: 'absolute',
        left: mod.x,
        top: mod.y,
        width: mod.w,
        height: mod.h,
        padding: 0,
        cursor: inZone ? 'pointer' : 'default',
        border: `3px solid ${accent}`,
        borderRadius: 6,
        background: surface,
        boxShadow: inZone
          ? `0 0 0 4px rgba(255,255,255,0.6), 0 0 18px 4px ${accent}aa`
          : '0 2px 6px rgba(0,0,0,0.25)',
        transition: 'box-shadow 160ms ease, transform 160ms ease',
        transform: inZone ? 'translateY(-2px)' : 'none',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <div
        style={{
          background: accent,
          color: '#fff',
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: 1,
          padding: '3px 8px',
          textAlign: 'left',
        }}
      >
        {label}
      </div>
      <div
        aria-hidden
        style={{
          flex: 1,
          position: 'relative',
          padding: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: accent,
          fontSize: 11,
          fontWeight: 600,
          opacity: 0.75,
        }}
      >
        {isSticky ? `${itemCount} note${itemCount === 1 ? '' : 's'}` : `${itemCount} stroke${itemCount === 1 ? '' : 's'}`}
        {inZone ? <span style={{ marginLeft: 8 }}>· press E</span> : null}
      </div>
    </button>
  );
}
