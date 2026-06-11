import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';
import type { PartiesListResponse, PartyListEntry } from '../api/types';
import PartyPreview from '../components/PartyPreview';
import PartyPeekModal from '../components/PartyPeekModal';
import { useSession } from '../hooks/useSession';

export default function Lobby() {
  const session = useSession();
  const navigate = useNavigate();
  const [parties, setParties] = useState<PartyListEntry[] | null>(null);
  const [peekSlug, setPeekSlug] = useState<string | null>(null);

  useEffect(() => {
    if (session.status !== 'authed') return;
    apiGet<PartiesListResponse>('/api/parties')
      .then((res) => setParties(res.parties))
      .catch(() => setParties([]));
  }, [session.status]);

  if (session.status !== 'authed') return null;

  return (
    <main
      style={{
        maxWidth: 'min(1100px, 92vw)',
        margin: 'clamp(24px, 6vh, 40px) auto',
        padding: 'clamp(16px, 4vw, 24px)',
      }}
    >
      <div className="op-plate">
        <p className="op-label" style={{ margin: '0 0 6px' }}>
          // {parties?.length ?? 0} rooms open
        </p>
        <h1 style={{ fontSize: 'clamp(24px, 5vw, 38px)', margin: 0, lineHeight: 1 }}>
          Pick a party,{' '}
          <span style={{ color: 'var(--op-coral)' }}>{session.user.username}</span>
        </h1>
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(300px, 100%), 1fr))',
          gap: 22,
          marginTop: 22,
        }}
      >
        {parties === null && (
          <p style={{ fontFamily: 'var(--op-font-mono)', color: 'var(--op-muted)' }}>
            Loading parties…
          </p>
        )}
        {parties?.map((p) => (
          <div
            key={p.slug}
            className="op-card op-lobby-card"
            style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}
          >
            <button
              type="button"
              onClick={() => navigate(`/party/${p.slug}`)}
              aria-label={p.name}
              style={{
                all: 'unset',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <div style={{ borderBottom: 'var(--op-bw-thick) solid var(--op-ink)' }}>
                <PartyPreview party={p} />
              </div>
              <div style={{ padding: '16px 18px 0' }}>
                <strong style={{ fontSize: 'clamp(18px, 2.5vw, 22px)', fontWeight: 900, letterSpacing: '-0.5px' }}>
                  {p.name}
                </strong>
                <p
                  style={{
                    margin: '5px 0 0',
                    color: 'var(--op-muted)',
                    fontFamily: 'var(--op-font-mono)',
                    fontSize: 11.5,
                    lineHeight: 1.5,
                  }}
                >
                  {p.description}
                </p>
              </div>
            </button>
            <div
              data-testid={`occupancy-${p.slug}`}
              style={{ display: 'flex', gap: 8, flexWrap: 'wrap', padding: '14px 18px 0' }}
            >
              <span className="op-pill op-pill--h">
                <span className="op-pill__b" />
                {p.occupancy.humans} humans
              </span>
              <span className="op-pill op-pill--a">
                <span className="op-pill__b" />
                {p.occupancy.agents} agents
              </span>
              <span className="op-pill op-pill--live">
                <span className="op-pill__b" />
                {p.occupancy.active_last_5min} active
              </span>
            </div>
            <div style={{ padding: '16px 18px 18px', marginTop: 'auto' }}>
              <button
                type="button"
                className="op-btn op-btn--yellow"
                onClick={() => setPeekSlug(p.slug)}
                style={{ fontSize: 12, padding: '8px 16px', borderRadius: 'var(--op-radius-sm)' }}
              >
                👁 Peek
              </button>
            </div>
          </div>
        ))}
      </div>
      {peekSlug !== null && (
        <PartyPeekModal
          slug={peekSlug}
          party={parties?.find((p) => p.slug === peekSlug)}
          onClose={() => setPeekSlug(null)}
        />
      )}
    </main>
  );
}
