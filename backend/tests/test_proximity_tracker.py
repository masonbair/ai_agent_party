from tests.conftest import join_party, register_human


def test_tracker_cleared_on_leave(client, store):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")

    # Alice polls with ?since=0 — establishes a tracker entry via observe_since_scoped.
    client.get(
        "/api/parties/cream-terrazzo/observe",
        params={
            "principal_id": a["principal"]["id"],
            "principal_kind": a["principal"]["kind"],
            "since": 0,
        },
    )

    # Internal check via the injected store fixture.
    world = store.get_or_create_world("cream-terrazzo")
    assert a["principal"]["id"] in world._proximity_trackers

    # Alice leaves → tracker cleared.
    client.post(
        "/api/parties/cream-terrazzo/leave",
        json={"principal": a["principal"]},
    )
    assert a["principal"]["id"] not in world._proximity_trackers


def test_tracker_diff_detects_entry_and_exit():
    from app.world import ProximityTracker

    t = ProximityTracker()
    entered_p, left_p, entered_m, left_m = t.diff(
        participants_in_range={"alice", "bob"},
        modules_in_rect={"draw-1"},
    )
    assert entered_p == {"alice", "bob"}
    assert left_p == set()
    assert entered_m == {"draw-1"}
    assert left_m == set()
    t.commit(participants_in_range={"alice", "bob"}, modules_in_rect={"draw-1"}, cursor=0)

    entered_p, left_p, entered_m, left_m = t.diff(
        participants_in_range={"bob", "carol"},
        modules_in_rect=set(),
    )
    assert entered_p == {"carol"}
    assert left_p == {"alice"}
    assert entered_m == set()
    assert left_m == {"draw-1"}
