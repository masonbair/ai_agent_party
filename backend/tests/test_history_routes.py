from app import db as db_module
from app.parties_data import PARTY_REGISTRY


def _slug() -> str:
    return next(iter(PARTY_REGISTRY))


def _send_chat(client, slug, text):
    a = client.post(
        "/api/agents", json={"username": "Bot1", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "agent", "id": a["agent_id"]}
    client.post(f"/api/parties/{slug}/join", json={"principal": principal})
    r = client.post(
        f"/api/parties/{slug}/chat",
        json={"principal": principal, "text": text},
    )
    assert r.status_code == 200


def test_broadcast_history_returns_messages_newest_first(client, store):
    slug = _slug()
    for i in range(3):
        _send_chat(client, slug, f"msg-{i}")
    r = client.get(f"/api/parties/{slug}/broadcast-history")
    assert r.status_code == 200
    body = r.json()
    assert [m["text"] for m in body["messages"]] == ["msg-2", "msg-1", "msg-0"]
    for m in body["messages"]:
        assert {"id", "party_slug", "sender_kind", "sender_id", "sender_name", "text", "at"}.issubset(m)
    assert body["next_before_id"] is None  # under page size


def test_broadcast_history_pagination(client, store):
    slug = _slug()
    # Seed via the db directly so we don't have to spam HTTP.
    for i in range(5):
        db_module.insert_broadcast(
            store.db,
            party_slug=slug,
            sender_kind="human",
            sender_id="sess",
            sender_name="Alice",
            text=f"m{i}",
            at=1000.0 + i,
        )
    r = client.get(f"/api/parties/{slug}/broadcast-history?limit=2")
    body = r.json()
    assert [m["text"] for m in body["messages"]] == ["m4", "m3"]
    assert body["next_before_id"] == body["messages"][-1]["id"]

    r2 = client.get(
        f"/api/parties/{slug}/broadcast-history"
        f"?limit=2&before_id={body['next_before_id']}"
    )
    body2 = r2.json()
    assert [m["text"] for m in body2["messages"]] == ["m2", "m1"]


def test_broadcast_history_404_unknown_slug(client):
    r = client.get("/api/parties/no-such-party/broadcast-history")
    assert r.status_code == 404


def test_broadcast_history_400_bad_limit(client):
    slug = _slug()
    r = client.get(f"/api/parties/{slug}/broadcast-history?limit=0")
    assert r.status_code == 400
    r2 = client.get(f"/api/parties/{slug}/broadcast-history?limit=abc")
    # non-int caught by FastAPI query parsing → 422 validation envelope
    assert r2.status_code == 422


def test_broadcast_history_400_bad_before_id(client):
    slug = _slug()
    r = client.get(f"/api/parties/{slug}/broadcast-history?before_id=-1")
    assert r.status_code == 400


def test_broadcast_history_is_party_scoped(client, store):
    # Insert into two different party slugs via DB directly.
    db_module.insert_broadcast(
        store.db, party_slug="cream-terrazzo", sender_kind="human",
        sender_id="s1", sender_name="A", text="for-cream", at=1.0,
    )
    db_module.insert_broadcast(
        store.db, party_slug="other-party", sender_kind="human",
        sender_id="s2", sender_name="B", text="for-other", at=2.0,
    )
    # We can hit the endpoint for a slug that exists in the registry.
    slug = _slug()  # cream-terrazzo
    body = client.get(f"/api/parties/{slug}/broadcast-history").json()
    assert all(m["party_slug"] == slug for m in body["messages"])
    assert "for-other" not in [m["text"] for m in body["messages"]]
