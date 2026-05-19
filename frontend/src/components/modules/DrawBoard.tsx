import { useEffect, useRef, useState } from 'react';
import type { ModuleSnapshot, Stroke } from '../../api/types';
import type { Principal } from '../../api/party';
import { addStroke, voteClear } from '../../api/modules';

type Props = {
  mod: Extract<ModuleSnapshot, { kind: 'drawboard' }>;
  principal: Principal;
  slug: string;
  inZone: boolean;
  /** Ignored: board always fills its parent now. Kept for API stability. */
  fill?: boolean;
};

const WIDTH_PX: Record<Stroke['width'], number> = {
  thin: 2,
  med: 5,
  thick: 10,
};

const PALETTE = ['#ff6b9d', '#3a5a8c', '#4dd0e1', '#ffb74d', '#81c784', '#222'];

function localFromPointer(
  e: React.PointerEvent<HTMLDivElement>,
  modW: number,
  modH: number,
): { x: number; y: number } {
  const rect = e.currentTarget.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return { x: 0, y: 0 };
  return {
    x: ((e.clientX - rect.left) / rect.width) * modW,
    y: ((e.clientY - rect.top) / rect.height) * modH,
  };
}

export function DrawBoard({ mod, principal, slug, inZone }: Props) {
  const [color, setColor] = useState(PALETTE[0]);
  const [width, setWidth] = useState<Stroke['width']>('med');
  const drawing = useRef<{ x: number; y: number }[] | null>(null);
  const [drafting, setDrafting] = useState<{ x: number; y: number }[]>([]);

  // Reset any in-flight stroke if the user walks out of range mid-drag.
  useEffect(() => {
    if (!inZone) {
      drawing.current = null;
      setDrafting([]);
    }
  }, [inZone]);

  function start(e: React.PointerEvent<HTMLDivElement>) {
    if (!inZone) return;
    const p = localFromPointer(e, mod.w, mod.h);
    drawing.current = [p];
    setDrafting([p]);
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* some browsers won't allow capture; ignore */
    }
  }

  function move(e: React.PointerEvent<HTMLDivElement>) {
    if (!drawing.current) return;
    const p = localFromPointer(e, mod.w, mod.h);
    drawing.current.push(p);
    setDrafting(drawing.current.slice());
  }

  async function end(e: React.PointerEvent<HTMLDivElement>) {
    if (!drawing.current) return;
    const pts = drawing.current;
    drawing.current = null;
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* not captured */
    }
    try {
      await addStroke(slug, mod.id, principal, color, width, pts);
    } catch {
      /* swallow; the next observe will reconcile */
    } finally {
      setDrafting([]);
    }
  }

  return (
    <div
      className="drawboard"
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        touchAction: 'none',
        cursor: inZone ? 'crosshair' : 'default',
      }}
      onPointerDown={start}
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
    >
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${mod.w} ${mod.h}`}
        preserveAspectRatio="none"
        style={{ position: 'absolute', inset: 0, display: 'block' }}
      >
        {mod.strokes.map((s) => (
          <polyline
            key={s.id}
            points={s.points.map((p) => `${p.x},${p.y}`).join(' ')}
            stroke={s.color}
            strokeWidth={WIDTH_PX[s.width]}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {drafting.length > 1 && (
          <polyline
            points={drafting.map((p) => `${p.x},${p.y}`).join(' ')}
            stroke={color}
            strokeWidth={WIDTH_PX[width]}
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
            opacity={0.7}
          />
        )}
      </svg>
      <div
        className="drawboard-toolbar"
        onPointerDown={(e) => e.stopPropagation()}
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          right: 8,
          display: 'flex',
          gap: 6,
          alignItems: 'center',
          background: 'rgba(255,255,255,0.92)',
          padding: '4px 8px',
          borderRadius: 6,
          boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
          fontSize: 12,
        }}
      >
        {PALETTE.map((c) => (
          <button
            key={c}
            type="button"
            aria-label={`Color ${c}`}
            onClick={() => setColor(c)}
            style={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              background: c,
              border: c === color ? '3px solid #222' : '1px solid #999',
              padding: 0,
              cursor: 'pointer',
            }}
          />
        ))}
        <span style={{ width: 1, height: 16, background: '#ccc' }} />
        {(['thin', 'med', 'thick'] as Stroke['width'][]).map((w) => (
          <button
            key={w}
            type="button"
            aria-label={`Width ${w}`}
            onClick={() => setWidth(w)}
            style={{
              border: w === width ? '2px solid #222' : '1px solid #888',
              background: '#fff',
              padding: '2px 6px',
              borderRadius: 3,
              cursor: 'pointer',
              fontSize: 11,
            }}
          >
            {w}
          </button>
        ))}
        <span style={{ flex: 1 }} />
        <button
          type="button"
          disabled={!inZone}
          onClick={() => voteClear(slug, mod.id, principal)}
          style={{
            border: '1px solid #b00',
            background: inZone ? '#fff' : '#eee',
            color: '#b00',
            padding: '3px 8px',
            borderRadius: 3,
            cursor: inZone ? 'pointer' : 'not-allowed',
            fontSize: 11,
            fontWeight: 600,
          }}
        >
          Clear ({mod.vote.votes}/{mod.vote.needed})
        </button>
      </div>
    </div>
  );
}
