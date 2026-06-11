import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import PartySpace from '../components/PartySpace';
import { ApiError, apiGet } from '../api/client';
import type { PartyConfig } from '../api/types';
import { useSession } from '../hooks/useSession';
import { joinParty, leaveParty, moveInParty, type Principal } from '../api/party';
import { useRealtimeParty } from '../hooks/useRealtimeParty';
import { useSessionId } from '../contexts/SessionIdContext';

export default function Party() {
  const session = useSession();
  const navigate = useNavigate();
  const { setSessionId } = useSessionId();
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

  const ready = session.status === 'authed' && party !== null;
  const principal: Principal | null = ready
    ? { kind: 'human', id: session.user.session_id }
    : null;

  const handleTakeover = useCallback(() => {
    setSessionId(null);
    navigate('/?takeover=1', { replace: true });
  }, [navigate, setSessionId]);

  const {
    participants,
    status: realtimeStatus,
    reactions,
    lighting,
    modules,
    applyObserveInitial,
    bubbles,
  } = useRealtimeParty(
    ready && principal
      ? { slug: party!.slug, principal, onEvicted: handleTakeover }
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
    <main
      style={{
        // Center the whole stack (header + room + chat) vertically so the gap
        // above the header matches the gap below the chat bar.
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        minHeight: '100vh',
      }}
    >
      <header
        style={{
          padding: 'clamp(6px, 1.2vw, 10px) clamp(12px, 3vw, 24px)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div className="op-plate" style={{ padding: '5px 14px' }}>
          <p className="op-label" style={{ margin: 0, fontSize: 9.5 }}>
            // you're in the room
          </p>
          <h1 style={{ margin: 0, fontSize: 'clamp(20px, 3.6vw, 28px)', lineHeight: 1.05 }}>
            {party.name}
          </h1>
        </div>
        {principal ? (
          <div
            aria-live="polite"
            className="op-plate"
            style={{
              padding: '7px 16px',
              borderRadius: 999,
              fontFamily: 'var(--op-font-mono)',
              fontSize: 12.5,
              fontWeight: 700,
              lineHeight: 1.5,
              color: 'var(--op-ink)',
            }}
          >
            press <kbd>R</kbd> to react · walk near a board and press <kbd>E</kbd> to interact
          </div>
        ) : null}
        <button
          type="button"
          className="op-btn op-btn--ink"
          onClick={() => navigate('/lobby')}
          style={{ fontSize: 13, padding: '10px 18px', borderRadius: 999 }}
        >
          ← Leave party
        </button>
      </header>
      <PartySpace
        party={party}
        user={session.user}
        participants={participants}
        onMove={onMove}
        principal={principal ?? undefined}
        modules={modules}
        lighting={lighting}
        reactions={reactions}
        applyObserveInitial={applyObserveInitial}
        bubbles={bubbles}
        slug={party.slug}
        status={realtimeStatus}
      />
    </main>
  );
}
