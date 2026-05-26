import { useEffect } from 'react';
import type { ModuleSnapshot } from '../../api/types';
import type { Principal } from '../../api/party';
import { StickyWall } from './StickyWall';
import { DrawBoard } from './DrawBoard';

type Props = {
  mod: Extract<ModuleSnapshot, { kind: 'stickynotes' | 'drawboard' }>;
  principal: Principal;
  slug: string;
  inZone: boolean;
  onClose: () => void;
};

export function ModuleModal({ mod, principal, slug, inZone, onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const isSticky = mod.kind === 'stickynotes';
  const accent = isSticky ? '#c89b4a' : '#3a5a8c';
  const title = isSticky ? 'Note Board' : 'White Board';

  // The editor renders at its own CSS size; stored coords are in module-local
  // space (0..mod.w / 0..mod.h) and rendered via percentages so the same DOM
  // is correct at any display size. The container caps to 85vw / 70vh while
  // preserving the module's native aspect ratio.
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(20, 20, 30, 0.55)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          borderRadius: 14,
          boxShadow: '0 30px 80px rgba(0,0,0,0.45)',
          padding: '14px 18px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          border: `3px solid ${accent}`,
          width: 'min(85vw, 900px)',
        }}
      >
        <header
          style={{
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          <h2
            style={{
              margin: 0,
              fontSize: 18,
              fontWeight: 700,
              color: accent,
              letterSpacing: 0.4,
            }}
          >
            {title}
          </h2>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {!inZone && (
              <span
                style={{
                  fontSize: 12,
                  color: '#a35a00',
                  background: '#fff5e0',
                  padding: '3px 8px',
                  borderRadius: 4,
                }}
              >
                walk closer to edit
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              style={{
                background: 'transparent',
                border: 'none',
                fontSize: 14,
                cursor: 'pointer',
                color: accent,
                lineHeight: 1,
              }}
            >
              esc
            </button>
          </div>
        </header>
        <div
          style={{
            position: 'relative',
            width: '100%',
            aspectRatio: `${mod.w} / ${mod.h}`,
            maxHeight: '70vh',
            overflow: 'hidden',
            borderRadius: 8,
            background: isSticky ? '#c89464' : '#fafafa',
            border: `1px solid ${accent}33`,
          }}
        >
          {mod.kind === 'stickynotes' ? (
            <StickyWall
              mod={mod}
              principal={principal}
              slug={slug}
              inZone={inZone}
              fill
            />
          ) : (
            <DrawBoard
              mod={mod}
              principal={principal}
              slug={slug}
              inZone={inZone}
              fill
            />
          )}
        </div>
      </div>
    </div>
  );
}
