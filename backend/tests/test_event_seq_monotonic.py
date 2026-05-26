"""`seq` is a monotonic, strictly-increasing counter spanning ALL event
types in a single party world. Agents rely on this to order events
without per-type bookkeeping.
"""
from tests.conftest import register_human, join_party


def test_seq_strictly_monotonic_across_types(client):
    alice = register_human(client, username="Alice")
    bob = register_human(client, username="Bob")
    join_party(client, alice, "cream-terrazzo")
    join_party(client, bob, "cream-terrazzo")

    # Drive a mix of event types.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": alice["principal"], "x": 200.0, "y": 200.0},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": alice["principal"], "text": "hello world"},
    )
    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": bob["principal"], "emoji": "🔥"},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": bob["principal"], "x": 250.0, "y": 250.0},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": bob["principal"], "text": "hi alice"},
    )
    client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": alice["principal"]},
    )

    diff = client.get("/api/parties/cream-terrazzo/observe?since=0").json()
    events = diff["events"]
    assert len(events) >= 6
    seqs = [e["seq"] for e in events]
    # Strictly monotonic.
    assert seqs == sorted(seqs), f"events not sorted by seq: {seqs}"
    assert len(set(seqs)) == len(seqs), f"duplicate seqs: {seqs}"
    # Per-type subsequences are also monotonic (each subset preserves global order).
    for t in {"move", "chat", "reaction", "join", "leave"}:
        sub = [e["seq"] for e in events if e["type"] == t]
        assert sub == sorted(sub), f"non-monotonic within {t}: {sub}"
    # Cursor equals max seq.
    assert diff["cursor"] == max(seqs)
