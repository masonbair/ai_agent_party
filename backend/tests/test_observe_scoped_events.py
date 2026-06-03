from tests.conftest import join_party, register_human


def _observe(client, principal, since):
    return client.get(
        "/api/parties/cream-terrazzo/observe",
        params={
            "principal_id": principal["principal"]["id"],
            "principal_kind": principal["principal"]["kind"],
            "since": since,
        },
    ).json()


def test_chat_from_far_participant_is_dropped(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)
    cur = _observe(client, a, since=0)["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": b["principal"], "text": "hello from far away"},
    )

    diff = _observe(client, a, since=cur)
    chats = [e for e in diff["events"] if e["type"] == "chat"]
    assert chats == [], "Bob's chat should be inaudible from across the room"


def test_chat_from_nearby_participant_passes(client):
    a = register_human(client, username="Alice")
    c = register_human(client, username="Carol")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    join_party(client, c, "cream-terrazzo", x=200, y=150)
    cur = _observe(client, a, since=0)["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": c["principal"], "text": "hi neighbor"},
    )
    diff = _observe(client, a, since=cur)
    chats = [e for e in diff["events"] if e["type"] == "chat"]
    assert any(c["text"] == "hi neighbor" for c in chats)


def test_far_move_is_dropped(client):
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)
    cur = _observe(client, a, since=0)["cursor"]

    # Bob moves but stays far.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": b["principal"], "x": 740, "y": 440},
    )
    diff = _observe(client, a, since=cur)
    moves = [e for e in diff["events"] if e["type"] == "move"]
    assert moves == []


def test_lighting_change_always_visible(client):
    # room_wide events bypass proximity scoping.
    a = register_human(client, username="Alice")
    b = register_human(client, username="Bob")
    join_party(client, a, "cream-terrazzo", x=50, y=50)
    join_party(client, b, "cream-terrazzo", x=750, y=450)
    cur = _observe(client, a, since=0)["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": b["principal"], "preset": "night"},
    )
    diff = _observe(client, a, since=cur)
    lights = [e for e in diff["events"] if e["type"] == "lighting_changed"]
    assert len(lights) == 1


def test_reaction_far_dropped_near_kept(client):
    a = register_human(client, username="Alice")
    far = register_human(client, username="Far")
    near = register_human(client, username="Near")
    join_party(client, a, "cream-terrazzo", x=100, y=100)
    join_party(client, far, "cream-terrazzo", x=700, y=400)
    join_party(client, near, "cream-terrazzo", x=180, y=180)
    cur = _observe(client, a, since=0)["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": far["principal"], "emoji": "🔥"},
    )
    client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": near["principal"], "emoji": "👍"},
    )
    diff = _observe(client, a, since=cur)
    rx = [e for e in diff["events"] if e["type"] == "reaction"]
    emojis = {r["emoji"] for r in rx}
    assert "🔥" not in emojis
    assert "👍" in emojis
