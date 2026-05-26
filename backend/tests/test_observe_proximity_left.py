from tests.conftest import join_party, register_human


def _observe(client, principal, since=None):
    params = {
        "principal_id": principal["principal"]["id"],
        "principal_kind": principal["principal"]["kind"],
    }
    if since is not None:
        params["since"] = since
    return client.get(
        "/api/parties/cream-terrazzo/observe", params=params
    ).json()


def _move(client, sess, x, y):
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": sess["principal"], "x": x, "y": y},
    )


def test_walking_out_of_participant_proximity_fires_proximity_left(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    join_party(client, b, "cream-terrazzo", x=200, y=150)  # in range
    # Establish baseline.
    cur = _observe(client, a)["cursor"]

    # Alice walks away — Bob exits her bubble.
    _move(client, a, 600, 400)

    diff = _observe(client, a, since=cur)
    leaves = [
        e for e in diff["events"]
        if e["type"] == "proximity_left"
        and e["left"]["kind"] == "participant"
        and e["left"]["id"] == b["principal"]["id"]
    ]
    assert len(leaves) == 1

    # No repeat on next poll.
    diff2 = _observe(client, a, since=diff["cursor"])
    repeats = [
        e for e in diff2["events"] if e["type"] == "proximity_left"
    ]
    assert repeats == []


def test_walking_out_of_module_rect_fires_proximity_left(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")
    ir = sticky["interactionRect"]
    _move(client, a, ir["x"] + ir["w"] / 2, ir["y"] + ir["h"] / 2)

    # Baseline observe — tracker now records Alice inside the sticky rect.
    cur = _observe(client, a)["cursor"]

    # Alice walks away.
    _move(client, a, 400, 100)

    diff = _observe(client, a, since=cur)
    leaves = [
        e for e in diff["events"]
        if e["type"] == "proximity_left"
        and e["left"] == {"kind": "module", "id": sticky["id"]}
    ]
    assert len(leaves) == 1
