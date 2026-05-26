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


def test_notes_hidden_when_requester_not_in_module_rect(client):
    # Bug reproduction: Alice writes a note; Bob — standing across the
    # room — should NOT see the note contents in /observe.
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")

    # Find the sticky module from an unscoped initial observe.
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")

    _move_into(client, a, sticky)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={
            "principal": a["principal"],
            "text": "private",
            "color": "yellow",
            "x": 10,
            "y": 10,
        },
    )

    # Bob stays at spawn (far from sticky), and asks for a scoped observe.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 600, "y": 100},
    )
    obs = _observe(client, b)
    bob_sticky = next(m for m in obs["modules"] if m["id"] == sticky["id"])
    # The stub does not include `notes`.
    assert "notes" not in bob_sticky, (
        "Bob is not at the noteboard — note contents must be hidden"
    )


def test_notes_visible_when_requester_in_module_rect(client):
    a = register_human(client, username="Alice")
    join_party(client, a, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")
    _move_into(client, a, sticky)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={"principal": a["principal"], "text": "hi",
              "color": "yellow", "x": 10, "y": 10},
    )
    obs = _observe(client, a)
    sticky2 = next(m for m in obs["modules"] if m["id"] == sticky["id"])
    assert sticky2.get("notes"), "Alice is at the noteboard — should see notes"
    assert sticky2["notes"][0]["text"] == "hi"


def test_strokes_and_vote_hidden_when_not_at_drawboard(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    draw = next(m for m in initial["modules"] if m["kind"] == "drawboard")
    _move_into(client, a, draw)
    client.post(
        f"/api/parties/cream-terrazzo/modules/{draw['id']}/strokes",
        json={
            "principal": a["principal"],
            "color": "#ffd54f",
            "width": "med",
            "points": [{"x": 1, "y": 1}, {"x": 2, "y": 2}],
        },
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 100, "y": 100},
    )
    obs = _observe(client, b)
    db = next(m for m in obs["modules"] if m["id"] == draw["id"])
    assert "strokes" not in db
    assert "vote" not in db


def test_module_event_only_delivered_to_in_rect_requester(client):
    # While Bob is not in the noteboard rect, a note_created emitted by
    # Alice should NOT appear in Bob's diff.
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo")
    join_party(client, b, "cream-terrazzo")
    initial = client.get("/api/parties/cream-terrazzo/observe").json()
    sticky = next(m for m in initial["modules"] if m["kind"] == "stickynotes")
    _move_into(client, a, sticky)
    # Bob takes a cursor far from the sticky module.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 600, "y": 100},
    )
    cur = _observe(client, b)["cursor"]

    client.post(
        f"/api/parties/cream-terrazzo/modules/{sticky['id']}/notes",
        json={"principal": a["principal"], "text": "secret",
              "color": "yellow", "x": 10, "y": 10},
    )
    diff = _observe(client, b, since=cur)
    note_events = [e for e in diff["events"] if e["type"] == "note_created"]
    assert note_events == []
