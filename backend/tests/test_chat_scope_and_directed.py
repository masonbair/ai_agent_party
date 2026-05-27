"""Tests for to_id, reply_to, and scope on POST /chat."""
from tests.conftest import join_party as _jp
from tests.conftest import register_agent as _ra

_SLUG = "cream-terrazzo"


def test_chat_carries_to_id(client) -> None:
    a = _ra(client, username="Alice")
    b = _ra(client, username="Bob", color="#ff6b9d")
    _jp(client, a, _SLUG)
    _jp(client, b, _SLUG)
    r = client.post(
        f"/api/parties/{_SLUG}/chat",
        json={
            "principal": {"kind": "agent", "id": a["agent_id"]},
            "text": "for you Bob",
            "to_id": b["agent_id"],
        },
    )
    assert r.status_code == 200
    obs = client.get(f"/api/parties/{_SLUG}/observe").json()
    chat = obs["recent_chat"][-1]
    assert chat["to_id"] == b["agent_id"]


def test_chat_to_id_unknown_is_404(client) -> None:
    a = _ra(client)
    _jp(client, a, _SLUG)
    r = client.post(
        f"/api/parties/{_SLUG}/chat",
        json={
            "principal": {"kind": "agent", "id": a["agent_id"]},
            "text": "hi",
            "to_id": "no-such-participant",
        },
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "recipient_unknown"


def test_chat_reply_to_valid(client) -> None:
    a = _ra(client, username="Alice")
    b = _ra(client, username="Bob", color="#ff6b9d")
    _jp(client, a, _SLUG)
    _jp(client, b, _SLUG)
    client.post(
        f"/api/parties/{_SLUG}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "first"},
    )
    obs = client.get(f"/api/parties/{_SLUG}/observe").json()
    first_seq = obs["recent_chat"][-1]["seq"]
    r = client.post(
        f"/api/parties/{_SLUG}/chat",
        json={"principal": {"kind": "agent", "id": b["agent_id"]},
              "text": "reply", "reply_to": first_seq},
    )
    assert r.status_code == 200
    obs2 = client.get(f"/api/parties/{_SLUG}/observe").json()
    assert obs2["recent_chat"][-1]["reply_to"] == first_seq


def test_chat_reply_to_unknown_is_404(client) -> None:
    a = _ra(client)
    _jp(client, a, _SLUG)
    r = client.post(
        f"/api/parties/{_SLUG}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hi", "reply_to": 99999},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "invalid_reply_to"


def test_chat_reply_to_non_chat_seq_is_404(client) -> None:
    # join produces a seq=1 event but it is JoinEvent, not a chat. reply_to
    # must reference a chat seq specifically.
    a = _ra(client)
    _jp(client, a, _SLUG)
    r = client.post(
        f"/api/parties/{_SLUG}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hi", "reply_to": 1},
    )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "invalid_reply_to"


def test_chat_scope_room_sets_room_wide(client) -> None:
    a = _ra(client)
    _jp(client, a, _SLUG)
    r = client.post(
        f"/api/parties/{_SLUG}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "everyone listen up", "scope": "room"},
    )
    assert r.status_code == 200
    obs = client.get(f"/api/parties/{_SLUG}/observe").json()
    chat = obs["recent_chat"][-1]
    assert chat["room_wide"] is True


def test_chat_scope_default_proximity_is_not_room_wide(client) -> None:
    a = _ra(client)
    _jp(client, a, _SLUG)
    client.post(
        f"/api/parties/{_SLUG}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "quiet hello"},
    )
    obs = client.get(f"/api/parties/{_SLUG}/observe").json()
    assert obs["recent_chat"][-1]["room_wide"] is False


def test_chat_scope_invalid_value_is_422(client) -> None:
    a = _ra(client)
    _jp(client, a, _SLUG)
    r = client.post(
        f"/api/parties/{_SLUG}/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hi", "scope": "everyone"},
    )
    # Pydantic Literal validation surfaces as 422.
    assert r.status_code == 422
