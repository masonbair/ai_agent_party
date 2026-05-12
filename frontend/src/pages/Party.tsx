import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PartySpace from '../components/PartySpace';
import { ApiError, apiGet } from '../api/client';
import type { PartyConfig } from '../api/types';
import { useSession } from '../hooks/useSession';

export default function Party() {
  const session = useSession();
  const navigate = useNavigate();
  const { slug } = useParams<{ slug: string }>();
  const [party, setParty] = useState<PartyConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug || session.status !== 'authed') return;
    apiGet<PartyConfig>(`/api/parties/${slug}`)
      .then(setParty)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 404) {
          setError('Party not found');
          navigate('/lobby', { replace: true });
        } else {
          setError('Failed to load party');
        }
      });
  }, [slug, session.status, navigate]);

  if (session.status !== 'authed') return null;
  if (error && !party) return <p role="alert">{error}</p>;
  if (!party) return <p>Loading party…</p>;

  return (
    <main>
      <header style={{ padding: '16px 24px', display: 'flex', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>{party.name}</h1>
        <button type="button" onClick={() => navigate('/lobby')}>
          Leave party
        </button>
      </header>
      <PartySpace party={party} user={session.user} />
    </main>
  );
}
