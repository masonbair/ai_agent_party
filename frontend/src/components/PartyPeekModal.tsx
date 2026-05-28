import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';
import type { PartyConfig, PartyPreviewResponse } from '../api/types';
import PartyPreview from './PartyPreview';

type Props = {
  slug: string;
  party?: PartyConfig;
  onClose: () => void;
};

type State =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'ready'; data: PartyPreviewResponse };

export default function PartyPeekModal({ slug, party, onClose }: Props) {
  const [state, setState] = useState<State>({ kind: 'loading' });

  useEffect(() => {
    let cancelled = false;
    apiGet<PartyPreviewResponse>(`/api/parties/${slug}/preview`)
      .then((data) => {
        if (!cancelled) setState({ kind: 'ready', data });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: 'error' });
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Preview ${slug}`}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: 20,
          width: 'min(560px, 92vw)',
          maxHeight: '90vh',
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {state.kind === 'loading' && <p>Loading preview…</p>}
        {state.kind === 'error' && (
          <>
            <p>Couldn't load preview.</p>
            <button type="button" onClick={onClose} aria-label="Close" style={{ alignSelf: 'flex-end' }}>
              Close
            </button>
          </>
        )}
        {state.kind === 'ready' && (
          <>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0 }}>{state.data.name}</h2>
              <button type="button" onClick={onClose} aria-label="Close">
                ×
              </button>
            </header>
            <p style={{ margin: 0, color: '#555' }}>{state.data.description}</p>
            {party && <PartyPreview party={party} />}
            <PartyPreviewBody data={state.data} />
          </>
        )}
        {state.kind === 'loading' && (
          <button type="button" onClick={onClose} aria-label="Close" style={{ alignSelf: 'flex-end' }}>
            Close
          </button>
        )}
      </div>
    </div>
  );
}

function PartyPreviewBody({ data }: { data: PartyPreviewResponse }) {
  const occ = data.occupancy;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div
        style={{
          padding: 10,
          background: '#f6f6f6',
          borderRadius: 8,
          fontSize: 14,
        }}
      >
        <div>
          {occ.humans} humans · {occ.agents} agents · {occ.active_last_5min} active
        </div>
        <div>Lighting: {data.lighting}</div>
        <div>Music: {data.music.label}</div>
      </div>
      <div>
        <strong style={{ fontSize: 13 }}>Recent chat</strong>
        {data.recent_chat.length === 0 ? (
          <p style={{ margin: '4px 0 0', color: '#888' }}>No recent chat.</p>
        ) : (
          <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
            {data.recent_chat.map((c) => (
              <li key={c.seq}>
                {c.actor_username}: {c.text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
