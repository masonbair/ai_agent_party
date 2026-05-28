import { useRef, useState } from 'react';
import type { ModuleSnapshot, StickyNote } from '../../api/types';
import type { Principal } from '../../api/party';
import { createNote, deleteNote, patchNote } from '../../api/modules';

type Props = {
  mod: Extract<ModuleSnapshot, { kind: 'stickynotes' }>;
  principal: Principal;
  slug: string;
  inZone: boolean;
  /** Ignored: wall always fills its parent now. Kept for API stability. */
  fill?: boolean;
};

const COLORS: StickyNote['color'][] = ['yellow', 'pink', 'blue', 'green'];
const NOTE_W_PCT = 22;
const NOTE_H_PCT = 26;

const SWATCH: Record<StickyNote['color'], string> = {
  yellow: '#fff4a3',
  pink: '#ffb8d1',
  blue: '#b6dcff',
  green: '#bff0c1',
};

function localFromEvent(
  e: { clientX: number; clientY: number },
  rect: DOMRect,
  modW: number,
  modH: number,
): { x: number; y: number } {
  if (rect.width === 0 || rect.height === 0) return { x: 0, y: 0 };
  return {
    x: ((e.clientX - rect.left) / rect.width) * modW,
    y: ((e.clientY - rect.top) / rect.height) * modH,
  };
}

export function StickyWall({ mod, principal, slug, inZone }: Props) {
  const wallRef = useRef<HTMLDivElement>(null);
  const [drafting, setDrafting] = useState<{ x: number; y: number } | null>(
    null,
  );
  const [draftText, setDraftText] = useState('');
  const [draftColor, setDraftColor] = useState<StickyNote['color']>('yellow');
  const [viewingId, setViewingId] = useState<string | null>(null);

  function handleWallClick(e: React.MouseEvent<HTMLDivElement>) {
    if (viewingId) {
      setViewingId(null);
      return;
    }
    if (!inZone || drafting) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setDrafting(localFromEvent(e, rect, mod.w, mod.h));
  }

  async function submitDraft() {
    if (!drafting || !draftText.trim()) return;
    try {
      await createNote(
        slug,
        mod.id,
        principal,
        draftText,
        draftColor,
        drafting.x,
        drafting.y,
      );
    } finally {
      setDrafting(null);
      setDraftText('');
    }
  }

  return (
    <div
      ref={wallRef}
      className="sticky-wall"
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
      }}
      onClick={handleWallClick}
    >
      {mod.notes.map((n) => (
        <NoteView
          key={n.id}
          note={n}
          modW={mod.w}
          modH={mod.h}
          canEdit={n.author_id === principal.id && inZone}
          wallRef={wallRef}
          viewing={viewingId === n.id}
          anyViewing={viewingId !== null}
          onView={() => setViewingId(n.id)}
          onCloseView={() => setViewingId(null)}
          onDelete={async () => {
            await deleteNote(slug, mod.id, n.id, principal);
          }}
          onEdit={async (patch) => {
            await patchNote(slug, mod.id, n.id, principal, patch);
          }}
        />
      ))}
      {inZone && !drafting && (
        <button
          type="button"
          className="sticky-add"
          aria-label="Add note"
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute',
            right: 12,
            top: 12,
            background: '#fff',
            border: '1px dashed #8a6a40',
            color: '#5b3a1e',
            padding: '6px 10px',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 600,
            cursor: 'default',
            pointerEvents: 'none',
            opacity: 0.85,
          }}
        >
          + click anywhere to add note
        </button>
      )}
      {drafting && (
        <div
          className="sticky-draft"
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute',
            left: `${(drafting.x / mod.w) * 100}%`,
            top: `${(drafting.y / mod.h) * 100}%`,
            transform: 'translate(-4px, -4px)',
            background: SWATCH[draftColor],
            padding: 8,
            borderRadius: 4,
            boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
            minWidth: 180,
            zIndex: 2,
          }}
        >
          <textarea
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                void submitDraft();
              }
            }}
            autoFocus
            rows={3}
            style={{
              border: 'none',
              background: 'transparent',
              outline: 'none',
              fontSize: 14,
              padding: 2,
              resize: 'none',
              fontFamily: 'inherit',
              width: '100%',
              whiteSpace: 'pre-wrap',
              overflowWrap: 'anywhere',
            }}
            placeholder="type your note (Enter = newline, ⌘/Ctrl+Enter = save)"
          />
          <div style={{ display: 'flex', gap: 4 }}>
            {COLORS.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={`Color ${c}`}
                onClick={() => setDraftColor(c)}
                style={{
                  width: 18,
                  height: 18,
                  border:
                    c === draftColor ? '2px solid #333' : '1px solid #888',
                  background: SWATCH[c],
                  borderRadius: 3,
                  cursor: 'pointer',
                  padding: 0,
                }}
              />
            ))}
            <span style={{ flex: 1 }} />
            <button
              type="button"
              onClick={submitDraft}
              style={{
                background: '#333',
                color: '#fff',
                border: 'none',
                padding: '3px 8px',
                borderRadius: 3,
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              save
            </button>
            <button
              type="button"
              onClick={() => setDrafting(null)}
              style={{
                background: 'transparent',
                border: '1px solid #888',
                padding: '3px 8px',
                borderRadius: 3,
                cursor: 'pointer',
                fontSize: 12,
              }}
            >
              cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function NoteView({
  note,
  modW,
  modH,
  canEdit,
  wallRef,
  viewing,
  anyViewing,
  onView,
  onCloseView,
  onDelete,
  onEdit,
}: {
  note: StickyNote;
  modW: number;
  modH: number;
  canEdit: boolean;
  wallRef: React.RefObject<HTMLDivElement>;
  viewing: boolean;
  anyViewing: boolean;
  onView: () => void;
  onCloseView: () => void;
  onDelete: () => Promise<void>;
  onEdit: (patch: { text?: string; x?: number; y?: number }) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(note.text);
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef<{
    pointerId: number;
    offsetX: number;
    offsetY: number;
    moved: boolean;
  } | null>(null);
  // Survives across the pointerup→click boundary so the click handler can
  // tell that the just-finished pointer sequence was a drag, not a tap.
  // (dragRef itself is cleared on pointerup, before click fires.)
  const wasDraggingRef = useRef(false);

  const displayX = dragPos ? dragPos.x : note.x;
  const displayY = dragPos ? dragPos.y : note.y;

  const baseStyle: React.CSSProperties = {
    position: 'absolute',
    left: `${(displayX / modW) * 100}%`,
    top: `${(displayY / modH) * 100}%`,
    width: `${NOTE_W_PCT}%`,
    minHeight: `${NOTE_H_PCT}%`,
    background: SWATCH[note.color],
    padding: 8,
    borderRadius: 3,
    boxShadow: dragPos
      ? '0 8px 18px rgba(0,0,0,0.35)'
      : '0 3px 6px rgba(0,0,0,0.25)',
    fontSize: 13,
    color: '#222',
    transform: dragPos ? 'rotate(-1deg) scale(1.04)' : 'rotate(-1deg)',
    overflow: 'hidden',
    cursor: canEdit && !editing ? 'grab' : 'pointer',
    touchAction: 'none',
    userSelect: 'none',
    zIndex: dragPos ? 3 : 1,
    transition:
      'left 220ms ease, top 220ms ease, width 220ms ease, ' +
      'min-height 220ms ease, transform 220ms ease, ' +
      'box-shadow 220ms ease, font-size 220ms ease, padding 220ms ease, ' +
      'border-radius 220ms ease',
  };

  const viewStyle: React.CSSProperties = viewing
    ? {
        left: '50%',
        top: '50%',
        width: '72%',
        minHeight: '60%',
        transform: 'translate(-50%, -50%) rotate(0deg) scale(1)',
        boxShadow: '0 24px 60px rgba(0,0,0,0.45)',
        fontSize: 22,
        padding: 24,
        borderRadius: 8,
        zIndex: 10,
        cursor: 'default',
      }
    : anyViewing
      ? { opacity: 0.55, pointerEvents: 'none' }
      : {};

  const common: React.CSSProperties = { ...baseStyle, ...viewStyle };

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (viewing || !canEdit || editing) return;
    const target = e.target as HTMLElement;
    if (target.closest('button')) return;
    const rect = wallRef.current?.getBoundingClientRect();
    if (!rect) return;
    const local = localFromEvent(e, rect, modW, modH);
    dragRef.current = {
      pointerId: e.pointerId,
      offsetX: local.x - note.x,
      offsetY: local.y - note.y,
      moved: false,
    };
    (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
    setDragPos({ x: note.x, y: note.y });
  }

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    const rect = wallRef.current?.getBoundingClientRect();
    if (!rect) return;
    const local = localFromEvent(e, rect, modW, modH);
    const nx = Math.max(0, Math.min(modW, local.x - drag.offsetX));
    const ny = Math.max(0, Math.min(modH, local.y - drag.offsetY));
    drag.moved = true;
    setDragPos({ x: nx, y: ny });
  }

  async function onPointerUp(e: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    wasDraggingRef.current = drag.moved;
    dragRef.current = null;
    const finalPos = dragPos;
    setDragPos(null);
    if (drag.moved && finalPos) {
      try {
        await onEdit({ x: finalPos.x, y: finalPos.y });
      } catch {
        /* optimistic UI; server diff will reconcile */
      }
    }
  }

  if (editing && canEdit) {
    return (
      <div onClick={(e) => e.stopPropagation()} style={common}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          style={{
            width: '100%',
            border: 'none',
            background: 'transparent',
            outline: 'none',
            fontSize: 13,
            resize: 'none',
            fontFamily: 'inherit',
            whiteSpace: 'pre-wrap',
            overflowWrap: 'anywhere',
          }}
        />
        <button
          onClick={async () => {
            await onEdit({ text });
            setEditing(false);
          }}
          style={{ marginTop: 4, fontSize: 11, padding: '2px 6px' }}
        >
          ok
        </button>
      </div>
    );
  }
  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        // Suppress the click that immediately follows a drag.
        if (wasDraggingRef.current) {
          wasDraggingRef.current = false;
          return;
        }
        if (viewing) {
          onCloseView();
          return;
        }
        const target = e.target as HTMLElement;
        if (target.closest('button')) return;
        onView();
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      style={common}
    >
      <div
        style={{
          whiteSpace: 'pre-wrap',
          overflowWrap: 'anywhere',
          wordBreak: 'break-word',
          lineHeight: 1.35,
        }}
      >
        {note.text}
      </div>
      {canEdit && !viewing && (
        <div
          style={{
            position: 'absolute',
            top: 2,
            right: 2,
            display: 'flex',
            gap: 4,
          }}
        >
          <button
            onClick={() => setEditing(true)}
            aria-label="Edit note"
            style={editBtn}
          >
            edit
          </button>
          <button onClick={onDelete} aria-label="Delete note" style={editBtn}>
            x
          </button>
        </div>
      )}
    </div>
  );
}

const editBtn: React.CSSProperties = {
  background: 'rgba(255,255,255,0.7)',
  border: '1px solid rgba(0,0,0,0.2)',
  fontSize: 10,
  padding: '1px 4px',
  cursor: 'pointer',
  borderRadius: 2,
};
