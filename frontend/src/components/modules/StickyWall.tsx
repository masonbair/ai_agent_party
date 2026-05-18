import { useState } from 'react';
import type { ModuleSnapshot, StickyNote } from '../../api/types';
import type { Principal } from '../../api/party';
import { createNote, deleteNote, patchNote } from '../../api/modules';

type Props = {
  mod: Extract<ModuleSnapshot, { kind: 'stickynotes' }>;
  principal: Principal;
  slug: string;
  inZone: boolean;
};

const COLORS: StickyNote['color'][] = ['yellow', 'pink', 'blue', 'green'];

export function StickyWall({ mod, principal, slug, inZone }: Props) {
  const [drafting, setDrafting] = useState<{ x: number; y: number } | null>(
    null,
  );
  const [draftText, setDraftText] = useState('');
  const [draftColor, setDraftColor] = useState<StickyNote['color']>('yellow');

  function handleWallClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!inZone || drafting) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setDrafting({ x: e.clientX - rect.left, y: e.clientY - rect.top });
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
        left: mod.x,
        top: mod.y,
        width: mod.w,
        height: mod.h,
      }}
      onClick={handleWallClick}
    >
      {mod.notes.map((n) => (
        <NoteView
          key={n.id}
          note={n}
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
        <button type="button" className="sticky-add" aria-label="Add note">
          + add note
        </button>
      )}
      {drafting && (
        <div
          className="sticky-draft"
          style={{ position: 'absolute', left: drafting.x, top: drafting.y }}
        >
          <input
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            autoFocus
          />
          <select
            value={draftColor}
            onChange={(e) =>
              setDraftColor(e.target.value as StickyNote['color'])
            }
          >
            {COLORS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <button type="button" onClick={submitDraft}>
            save
          </button>
          <button type="button" onClick={() => setDrafting(null)}>
            cancel
          </button>
        </div>
      )}
    </div>
  );
}

function NoteView({
  note,
  canEdit,
  onDelete,
  onEdit,
}: {
  note: StickyNote;
  canEdit: boolean;
  onDelete: () => Promise<void>;
  onEdit: (patch: { text?: string }) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(note.text);
  if (editing && canEdit) {
    return (
      <div
        className={`sticky-note sticky-${note.color}`}
        style={{ position: 'absolute', left: note.x, top: note.y }}
      >
        <input value={text} onChange={(e) => setText(e.target.value)} />
        <button
          onClick={async () => {
            await onEdit({ text });
            setEditing(false);
          }}
        >
          ok
        </button>
      </div>
    );
  }
  return (
    <div
      className={`sticky-note sticky-${note.color}`}
      style={{ position: 'absolute', left: note.x, top: note.y }}
    >
      <span>{note.text}</span>
      {canEdit && (
        <>
          <button onClick={() => setEditing(true)} aria-label="Edit note">
            edit
          </button>
          <button onClick={onDelete} aria-label="Delete note">
            x
          </button>
        </>
      )}
    </div>
  );
}
