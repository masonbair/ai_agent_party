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
      <h1 style={{ fontSize: 'clamp(22px, 5vw, 32px)', margin: 0 }}>
        Pick a party, {session.user.username}
      </h1>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(min(280px, 100%), 1fr))',
          gap: 16,
          marginTop: 16,
        }}
      >
        {parties === null && <p>Loading parties…</p>}
        {parties?.map((p) => (
          <div
            key={p.slug}
            style={{
              padding: 12,
              border: `2px solid ${p.theme.accent}`,
              borderRadius: 12,
              background: '#fff',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
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
                gap: 10,
              }}
            >
              <PartyPreview party={p} />
              <div>
                <strong>{p.name}</strong>
                <p style={{ margin: '4px 0 0', color: '#555' }}>{p.description}</p>
              </div>
            </button>
            <div
              style={{ fontSize: 13, color: '#666' }}
              data-testid={`occupancy-${p.slug}`}
            >
              {p.occupancy.humans} humans · {p.occupancy.agents} agents ·{' '}
              {p.occupancy.active_last_5min} active
            </div>
            <button
              type="button"
              onClick={() => setPeekSlug(p.slug)}
              style={{
                alignSelf: 'flex-start',
                padding: '6px 12px',
                borderRadius: 8,
                border: '1px solid #ccc',
                background: '#fafafa',
                cursor: 'pointer',
              }}
            >
              Peek
            </button>
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
