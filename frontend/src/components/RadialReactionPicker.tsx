import { useEffect, useState } from 'react';
import { REACTION_EMOJI, type ReactionEmoji } from '../api/types';

type Props = {
  open: boolean;
  anchorPercent: { x: number; y: number } | null; // 0..100 in world percent
  onPick: (emoji: ReactionEmoji) => void;
  onClose: () => void;
};

const RADIUS_PX = 76;
const BUTTON_PX = 44;
const EMOJI_PX = 22;
const ACTIVE_SCALE = 1.7;

export function RadialReactionPicker({
  open,
  anchorPercent,
  onPick,
  onClose,
}: Props) {
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    if (!open) return;
    setSelected(0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      const k = e.key.toLowerCase();
      if (k === 'escape' || k === 'r') {
        e.preventDefault();
        onClose();
        return;
      }
      if (k === 'enter' || k === ' ') {
        e.preventDefault();
        onPick(REACTION_EMOJI[selected]);
        onClose();
        return;
      }
      const step = (() => {
        if (k === 'a' || k === 'arrowleft') return -1;
        if (k === 'd' || k === 'arrowright') return 1;
        if (k === 'w' || k === 'arrowup') return -3;
        if (k === 's' || k === 'arrowdown') return 3;
        return 0;
      })();
      if (step !== 0) {
        e.preventDefault();
        setSelected((s) => (s + step + REACTION_EMOJI.length) % REACTION_EMOJI.length);
      }
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, selected, onPick, onClose]);

  if (!open || !anchorPercent) return null;

  return (
    <div
      role="menu"
      aria-label="React"
      data-testid="radial-reaction-picker"
      style={{
        position: 'absolute',
        left: `${anchorPercent.x}%`,
        top: `${anchorPercent.y}%`,
        width: 0,
        height: 0,
        pointerEvents: 'none',
        zIndex: 50,
      }}
    >
      {REACTION_EMOJI.map((emoji, i) => {
        const angle = (i / REACTION_EMOJI.length) * Math.PI * 2 - Math.PI / 2;
        const cx = Math.cos(angle) * RADIUS_PX;
        const cy = Math.sin(angle) * RADIUS_PX;
        const active = i === selected;
        return (
          <button
            key={emoji}
            type="button"
            role="menuitem"
            aria-label={`React with ${emoji}`}
            data-active={active ? 'true' : 'false'}
            onMouseEnter={() => setSelected(i)}
            onClick={(e) => {
              e.stopPropagation();
              onPick(emoji);
              onClose();
            }}
            style={{
              position: 'absolute',
              left: cx - BUTTON_PX / 2,
              top: cy - BUTTON_PX / 2,
              width: BUTTON_PX,
              height: BUTTON_PX,
              borderRadius: '50%',
              border: active ? '3px solid var(--op-coral)' : '3px solid var(--op-ink)',
              background: 'var(--op-paper)',
              boxShadow: active
                ? '3px 3px 0 var(--op-shadow), 0 0 0 4px var(--op-paper), 0 0 0 7px var(--op-coral)'
                : '3px 3px 0 var(--op-shadow)',
              cursor: 'pointer',
              pointerEvents: 'auto',
              fontSize: EMOJI_PX,
              lineHeight: 1,
              padding: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transform: active ? `scale(${ACTIVE_SCALE})` : 'scale(1)',
              zIndex: active ? 2 : 1,
              transition: 'transform 120ms ease, box-shadow 120ms ease',
            }}
          >
            {emoji}
          </button>
        );
      })}
    </div>
  );
}
