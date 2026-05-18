import { useRef, useState } from 'react';
import type { ModuleSnapshot, Stroke } from '../../api/types';
import type { Principal } from '../../api/party';
import { addStroke, voteClear } from '../../api/modules';

type Props = {
  mod: Extract<ModuleSnapshot, { kind: 'drawboard' }>;
  principal: Principal;
  slug: string;
  inZone: boolean;
};

const WIDTH_PX: Record<Stroke['width'], number> = {
  thin: 2,
  med: 5,
  thick: 10,
};

export function DrawBoard({ mod, principal, slug, inZone }: Props) {
  const [color] = useState('#ff6b9d');
  const [width] = useState<Stroke['width']>('med');
  const drawing = useRef<{ x: number; y: number }[] | null>(null);

  function start(e: React.PointerEvent<HTMLDivElement>) {
    if (!inZone) return;
    const r = e.currentTarget.getBoundingClientRect();
    drawing.current = [{ x: e.clientX - r.left, y: e.clientY - r.top }];
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function move(e: React.PointerEvent<HTMLDivElement>) {
    if (!drawing.current) return;
    const r = e.currentTarget.getBoundingClientRect();
    drawing.current.push({ x: e.clientX - r.left, y: e.clientY - r.top });
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
      /* swallow; observe will refresh */
    }
  }

  return (
    <div
      className="drawboard"
      style={{
        position: 'absolute',
        left: mod.x,
        top: mod.y,
        width: mod.w,
        height: mod.h,
        touchAction: 'none',
      }}
      onPointerDown={start}
      onPointerMove={move}
      onPointerUp={end}
      onPointerCancel={end}
    >
      <svg
        width={mod.w}
        height={mod.h}
        style={{ position: 'absolute', inset: 0 }}
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
          />
        ))}
      </svg>
      <div
        className="drawboard-toolbar"
        style={{ position: 'absolute', top: -28, left: 0 }}
      >
        <button
          type="button"
          disabled={!inZone}
          onClick={() => voteClear(slug, mod.id, principal)}
        >
          Clear ({mod.vote.votes}/{mod.vote.needed})
        </button>
      </div>
    </div>
  );
}
