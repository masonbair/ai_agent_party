import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PartySpace from '../components/PartySpace';
import { ApiError, apiGet } from '../api/client';
import type { PartyConfig } from '../api/types';
import { useSession, clearStoredSessionId } from '../hooks/useSession';
import { joinParty, leaveParty, moveInParty, type Principal } from '../api/party';
import { useRealtimeParty } from '../hooks/useRealtimeParty';

export default function Party() {
  const session = useSession();
  const navigate = useNavigate();
  const { slug } = useParams<{ slug: string }>();
  const [party, setParty] = useState<PartyConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [leaveHovered, setLeaveHovered] = useState(false);

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

  const ready = session.status === 'authed' && party !== null;
  const principal: Principal | null = ready
    ? { kind: 'human', id: session.user.session_id }
    : null;

  const { participants } = useRealtimeParty(
    ready && principal
      ? {
          slug: party!.slug,
          principal,
          onEvicted: () => {
            clearStoredSessionId();
            navigate('/?takeover=1', { replace: true });
          },
        }
      : { slug: '', principal: { kind: 'human', id: '' } },
  );

  useEffect(() => {
    if (!ready || !principal || !party) return;
    const slugForCleanup = party.slug;
    const pForCleanup = principal;
    joinParty(slugForCleanup, pForCleanup).catch(() => {});
    return () => {
      leaveParty(slugForCleanup, pForCleanup).catch(() => {});
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, party?.slug, principal?.id]);

  if (session.status !== 'authed') return null;
  if (error && !party) return <p role="alert">{error}</p>;
  if (!party) return <p>Loading party…</p>;

  const onMove = (x: number, y: number) => {
    if (!principal) return;
    moveInParty(party.slug, principal, x, y).catch(() => {});
  };

  return (
    <main>
      <header
        style={{
          padding: 'clamp(8px, 2vw, 16px) clamp(12px, 3vw, 24px)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <h1 style={{ margin: 0, fontSize: 'clamp(20px, 4vw, 28px)' }}>{party.name}</h1>
        <button
          type="button"
          onClick={() => navigate('/lobby')}
          onMouseEnter={() => setLeaveHovered(true)}
          onMouseLeave={() => setLeaveHovered(false)}
          style={{
            background: party.theme.accent,
            color: '#fff',
            border: 'none',
            padding: '8px 16px',
            borderRadius: 999,
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            transform: leaveHovered ? 'translateY(-1px)' : 'translateY(0)',
            boxShadow: leaveHovered
              ? '0 4px 10px rgba(0,0,0,0.15)'
              : '0 2px 6px rgba(0,0,0,0.10)',
            transition: 'transform 120ms ease, box-shadow 120ms ease',
          }}
        >
          ← Leave party
        </button>
      </header>
      <PartySpace
        party={party}
        user={session.user}
        participants={participants}
        onMove={onMove}
      />
    </main>
  );
}
