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
        background: 'rgba(27,23,20,0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        zIndex: 50,
      }}
      onClick={onClose}
    >
      <div
        className="op-card"
        style={{
          padding: 22,
          width: 'min(560px, 92vw)',
          maxHeight: '90vh',
          overflow: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 14,
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
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
              <h2 style={{ margin: 0, fontSize: 'clamp(20px, 4vw, 26px)' }}>{state.data.name}</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                style={{
                  flexShrink: 0,
                  width: 32,
                  height: 32,
                  borderRadius: 999,
                  border: '3px solid var(--op-ink)',
                  background: 'var(--op-paper)',
                  fontSize: 18,
                  fontWeight: 900,
                  lineHeight: 1,
                  cursor: 'pointer',
                  boxShadow: '2px 2px 0 var(--op-shadow)',
                }}
              >
                ×
              </button>
            </header>
            <p
              style={{
                margin: 0,
                color: 'var(--op-muted)',
                fontFamily: 'var(--op-font-mono)',
                fontSize: 12.5,
                lineHeight: 1.5,
              }}
            >
              {state.data.description}
            </p>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <span className="op-pill op-pill--h">
          <span className="op-pill__b" />
          {occ.humans} humans
        </span>
        <span className="op-pill op-pill--a">
          <span className="op-pill__b" />
          {occ.agents} agents
        </span>
        <span className="op-pill op-pill--live">
          <span className="op-pill__b" />
          {occ.active_last_5min} active
        </span>
      </div>
      <div
        style={{
          padding: '10px 12px',
          background: 'var(--op-paper-2)',
          border: '2px solid var(--op-ink)',
          borderRadius: 'var(--op-radius-sm)',
          fontFamily: 'var(--op-font-mono)',
          fontSize: 12,
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
        }}
      >
        <div>Lighting: {data.lighting}</div>
        <div>Music: {data.music.label}</div>
      </div>
      <div>
        <strong className="op-label" style={{ fontSize: 11 }}>
          Recent chat
        </strong>
        {data.recent_chat.length === 0 ? (
          <p style={{ margin: '6px 0 0', color: 'var(--op-faint)', fontFamily: 'var(--op-font-mono)', fontSize: 12 }}>
            No recent chat.
          </p>
        ) : (
          <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 13.5 }}>
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
