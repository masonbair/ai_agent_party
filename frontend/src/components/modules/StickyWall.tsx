import { useState } from 'react';
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
const NOTE_W_PCT = 22; // note card width as % of wall width
const NOTE_H_PCT = 26; // note card height as % of wall height

const SWATCH: Record<StickyNote['color'], string> = {
  yellow: '#fff4a3',
  pink: '#ffb8d1',
  blue: '#b6dcff',
  green: '#bff0c1',
};

function localFromEvent(
  e: React.MouseEvent<HTMLDivElement>,
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

export function StickyWall({ mod, principal, slug, inZone }: Props) {
  const [drafting, setDrafting] = useState<{ x: number; y: number } | null>(
    null,
  );
  const [draftText, setDraftText] = useState('');
  const [draftColor, setDraftColor] = useState<StickyNote['color']>('yellow');

  function handleWallClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!inZone || drafting) return;
    setDrafting(localFromEvent(e, mod.w, mod.h));
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
          <input
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            autoFocus
            style={{
              border: 'none',
              background: 'transparent',
              outline: 'none',
              fontSize: 14,
              padding: 2,
            }}
            placeholder="type your note"
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
  onDelete,
  onEdit,
}: {
  note: StickyNote;
  modW: number;
  modH: number;
  canEdit: boolean;
  onDelete: () => Promise<void>;
  onEdit: (patch: { text?: string }) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(note.text);
  const common: React.CSSProperties = {
    position: 'absolute',
    left: `${(note.x / modW) * 100}%`,
    top: `${(note.y / modH) * 100}%`,
    width: `${NOTE_W_PCT}%`,
    minHeight: `${NOTE_H_PCT}%`,
    background: SWATCH[note.color],
    padding: 8,
    borderRadius: 3,
    boxShadow: '0 3px 6px rgba(0,0,0,0.25)',
    fontSize: 13,
    color: '#222',
    transform: 'rotate(-1deg)',
    overflow: 'hidden',
  };
  if (editing && canEdit) {
    return (
      <div onClick={(e) => e.stopPropagation()} style={common}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          style={{
            width: '100%',
            border: 'none',
            background: 'transparent',
            outline: 'none',
            fontSize: 13,
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
    <div onClick={(e) => e.stopPropagation()} style={common}>
      <div style={{ wordBreak: 'break-word' }}>{note.text}</div>
      {canEdit && (
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
