import type { ModuleSnapshot } from '../../api/types';

type Props = {
  mod: Extract<ModuleSnapshot, { kind: 'stickynotes' | 'drawboard' }>;
  inZone: boolean;
  onOpen: () => void;
};

const CORK_BG =
  'repeating-radial-gradient(circle at 25% 30%, #c89464 0 1px, transparent 1px 6px),' +
  'repeating-radial-gradient(circle at 70% 60%, #b27b4d 0 1px, transparent 1px 7px),' +
  'linear-gradient(180deg, #d4a06a 0%, #b88358 100%)';

const WHITEBOARD_BG = 'linear-gradient(180deg, #fdfdfd 0%, #f1f3f6 100%)';

export function ModuleStructure({ mod, inZone, onOpen }: Props) {
  const isSticky = mod.kind === 'stickynotes';
  const label = isSticky ? 'NOTE BOARD' : 'WHITE BOARD';
  const itemCount =
    mod.kind === 'stickynotes' ? mod.notes.length : mod.strokes.length;
  const frame = isSticky ? '#5b3a1e' : '#7a7d83';
  const innerBg = isSticky ? CORK_BG : WHITEBOARD_BG;
  const labelBg = isSticky ? '#5b3a1e' : '#34373d';
  const glow = isSticky ? '#f0c987aa' : '#9fbde6aa';

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
        border: 'none',
        background: 'transparent',
        boxShadow: inZone
          ? `0 0 0 3px rgba(255,255,255,0.7), 0 0 22px 6px ${glow}`
          : 'none',
        transition: 'box-shadow 160ms ease, transform 160ms ease',
        transform: inZone ? 'translateY(-2px)' : 'none',
        borderRadius: 6,
      }}
    >
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: frame,
          borderRadius: 6,
          boxShadow:
            'inset 0 2px 0 rgba(255,255,255,0.18), 0 4px 10px rgba(0,0,0,0.35)',
          padding: 5,
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
        }}
      >
        <div
          style={{
            flex: 1,
            background: innerBg,
            borderRadius: 3,
            position: 'relative',
            overflow: 'hidden',
            boxShadow: 'inset 0 0 6px rgba(0,0,0,0.25)',
          }}
        >
          {isSticky ? <CorkPins /> : <WhiteboardMarks />}
        </div>
        <div
          style={{
            background: labelBg,
            color: '#fff',
            fontSize: 9,
            fontWeight: 800,
            letterSpacing: 1.2,
            padding: '2px 6px',
            borderRadius: 2,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span>{label}</span>
          <span style={{ opacity: 0.85, fontWeight: 600 }}>
            {isSticky
              ? `${itemCount} note${itemCount === 1 ? '' : 's'}`
              : `${itemCount} stroke${itemCount === 1 ? '' : 's'}`}
            {inZone ? ' · E' : ''}
          </span>
        </div>
      </div>
    </button>
  );
}

function CorkPins() {
  // A few decorative pinned squares so the cork board reads as a corkboard
  // even from a distance.
  const pins = [
    { left: '14%', top: '22%', color: '#fff5b6', rot: -6 },
    { left: '58%', top: '34%', color: '#ffb3c7', rot: 8 },
    { left: '32%', top: '64%', color: '#b8e0ff', rot: -3 },
  ];
  return (
    <>
      {pins.map((p, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            left: p.left,
            top: p.top,
            width: 18,
            height: 14,
            background: p.color,
            transform: `rotate(${p.rot}deg)`,
            boxShadow: '0 1px 2px rgba(0,0,0,0.3)',
            borderRadius: 1,
          }}
        />
      ))}
    </>
  );
}

function WhiteboardMarks() {
  // A few stray squiggles + marker-tray strip to read as a whiteboard.
  return (
    <>
      <svg
        width="100%"
        height="100%"
        viewBox="0 0 100 60"
        preserveAspectRatio="none"
        style={{ position: 'absolute', inset: 0 }}
      >
        <path
          d="M 12 18 q 10 -8 20 0 t 22 0"
          stroke="#ff6b9d"
          strokeWidth="1.4"
          fill="none"
          strokeLinecap="round"
        />
        <path
          d="M 18 36 l 8 6 l 12 -10"
          stroke="#3a5a8c"
          strokeWidth="1.4"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          bottom: 0,
          height: 5,
          background: 'linear-gradient(180deg, #b8bbc1 0%, #8a8d92 100%)',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.3)',
        }}
      />
    </>
  );
}
