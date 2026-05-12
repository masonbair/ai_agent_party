import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiGet } from '../api/client';
import type { PartiesListResponse, PartyConfig } from '../api/types';
import { useSession } from '../hooks/useSession';

export default function Lobby() {
  const session = useSession();
  const navigate = useNavigate();
  const [parties, setParties] = useState<PartyConfig[] | null>(null);

  useEffect(() => {
    if (session.status !== 'authed') return;
    apiGet<PartiesListResponse>('/api/parties')
      .then((res) => setParties(res.parties))
      .catch(() => setParties([]));
  }, [session.status]);

  if (session.status !== 'authed') return null;

  return (
    <main style={{ maxWidth: 900, margin: '40px auto', padding: 24 }}>
      <h1>Pick a party, {session.user.username}</h1>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
          gap: 16,
          marginTop: 16,
        }}
      >
        {parties === null && <p>Loading parties…</p>}
        {parties?.map((p) => (
          <button
            key={p.slug}
            type="button"
            onClick={() => navigate(`/party/${p.slug}`)}
            style={{
              textAlign: 'left',
              padding: 16,
              border: `2px solid ${p.theme.accent}`,
              borderRadius: 12,
              background: '#fff',
            }}
          >
            <div
              style={{
                height: 80,
                borderRadius: 8,
                background: p.theme.floor,
                marginBottom: 12,
              }}
            />
            <strong>{p.name}</strong>
            <p style={{ margin: '4px 0 0', color: '#555' }}>{p.description}</p>
          </button>
        ))}
      </div>
    </main>
  );
}
