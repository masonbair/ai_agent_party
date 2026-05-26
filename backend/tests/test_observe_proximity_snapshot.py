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


def _move_into(client, sess, module):
    ir = module["interactionRect"]
    cx = ir["x"] + ir["w"] / 2
    cy = ir["y"] + ir["h"] / 2
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": sess["principal"], "x": cx, "y": cy},
    )


def test_module_entry_fires_proximity_snapshot_once(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")

    # Pre-populate a note from another participant so the snapshot has content.
    b = register_human(client, username="Bob")
    join_party(client, b, "cream-terrazzo")
    _move_into(client, b, sticky)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={"principal": b["principal"], "text": "hello world",
              "color": "yellow", "x": 5, "y": 5},
    )
    # Bob steps away so Alice's entry is unambiguous.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 50, "y": 50},
    )

    # Alice's first scoped poll establishes baseline tracker state.
    obs0 = _observe(client, a)
    cur = obs0["cursor"]

    # Alice walks into the sticky rect.
    _move_into(client, a, sticky)
    diff = _observe(client, a, since=cur)
    snaps = [e for e in diff["events"] if e["type"] == "proximity_snapshot"]
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap["entered"] == {"kind": "module", "id": sticky["id"]}
    assert snap["module"] is not None
    assert any(n["text"] == "hello world" for n in snap["module"]["notes"])

    # Polling again WITHOUT moving — snapshot must NOT repeat.
    diff2 = _observe(client, a, since=diff["cursor"])
    repeats = [
        e for e in diff2["events"] if e["type"] == "proximity_snapshot"
    ]
    assert repeats == []


def test_participant_entry_fires_proximity_snapshot_with_recent_chat(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    # Bob is initially far from Alice.
    join_party(client, b, "cream-terrazzo", x=700, y=400)

    # Bob says things while far — Alice should NOT see them in real time.
    for i in range(3):
        client.post(
            "/api/parties/cream-terrazzo/chat",
            json={"principal": b["principal"], "text": f"far msg {i}"},
        )

    obs0 = _observe(client, a)
    cur = obs0["cursor"]

    # Bob walks into proximity of Alice.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 200, "y": 150},
    )

    diff = _observe(client, a, since=cur)
    snaps = [
        e for e in diff["events"]
        if e["type"] == "proximity_snapshot"
        and e["entered"]["kind"] == "participant"
        and e["entered"]["id"] == b["principal"]["id"]
    ]
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap["recent_chat"], "snapshot should include Bob's catch-up chats"
    texts = [c["text"] for c in snap["recent_chat"]]
    assert "far msg 2" in texts
