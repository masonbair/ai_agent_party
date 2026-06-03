from tests.conftest import join_party, register_human


def _observe(client, principal, since=None):
    params = {
        "principal_id": principal["principal"]["id"],
        "principal_kind": principal["principal"]["kind"],
    }
    if since is not None:
        params["since"] = since
    return client.get("/api/parties/cream-terrazzo/observe", params=params).json()


def test_initial_observe_hides_far_away_participants(client):
    # Alice spawns at (50, 50); Bob spawns at (750, 450) — distance > 180.
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)

    obs = _observe(client, a)
    ids = {p["id"] for p in obs["participants"]}
    assert a["principal"]["id"] in ids
    assert b["principal"]["id"] not in ids, (
        "Bob is across the room — should be hidden"
    )


def test_initial_observe_includes_in_range_participants(client):
    a = register_human(client, username="Alice")
    c = register_human(client, username="Carol")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    join_party(client, c, "cream-terrazzo", x=200, y=150)  # ~111 units away

    obs = _observe(client, a)
    ids = {p["id"] for p in obs["participants"]}
    assert c["principal"]["id"] in ids


def test_legacy_observe_without_principal_returns_all_participants(client):
    # Backwards compat: no principal_id → unscoped (frontend renderer relies
    # on this until it migrates).
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)

    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    ids = {p["id"] for p in obs["participants"]}
    assert {a["principal"]["id"], b["principal"]["id"]} <= ids
