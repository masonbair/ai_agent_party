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

// Fullscreen modal that wraps the StickyWall or DrawBoard editor. The party
// floor is blurred behind. Esc or backdrop click closes.
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

  // Render the editor at a comfortable on-screen size; the stored stroke /
  // note coordinates live in module-local space (0..mod.w / 0..mod.h) so the
  // editor's own DOM remains at native module dimensions inside a scaled
  // wrapper. This keeps existing pointer math correct.
  const scale = isSticky ? 3.6 : 4.2;

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
          maxWidth: '90vw',
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          gap: 10,
          border: `3px solid ${accent}`,
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
                fontSize: 18,
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
          // The editors are absolutely-positioned at mod.x/mod.y in their own
          // CSS; we re-anchor them by offsetting the container so they appear
          // at (0,0) inside a scaling wrapper.
          style={{
            position: 'relative',
            width: mod.w * scale,
            height: mod.h * scale,
            overflow: 'hidden',
            borderRadius: 8,
            background: '#f7f5ef',
          }}
        >
          <div
            style={{
              position: 'absolute',
              left: -mod.x * scale,
              top: -mod.y * scale,
              width: 0,
              height: 0,
              transformOrigin: 'top left',
              transform: `scale(${scale})`,
            }}
          >
            {mod.kind === 'stickynotes' ? (
              <StickyWall
                mod={mod}
                principal={principal}
                slug={slug}
                inZone={inZone}
              />
            ) : (
              <DrawBoard
                mod={mod}
                principal={principal}
                slug={slug}
                inZone={inZone}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
