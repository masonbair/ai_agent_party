"""Tests for @mention parsing and you_are_mentioned flagging."""
from tests.conftest import join_party as _jp
from tests.conftest import register_agent as _ra


def test_chat_attaches_mentions(client) -> None:
    a = _ra(client, username="Alice")
    b = _ra(client, username="Bob", color="#ff6b9d")
    _jp(client, a, "cream-terrazzo")
    _jp(client, b, "cream-terrazzo")
    # Use case-insensitive form to confirm the matcher folds case.
    r = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hi @bob and @nobody"},
    )
    assert r.status_code == 200
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    chat = [c for c in obs["recent_chat"] if c["actor_id"] == a["agent_id"]][-1]
    assert chat["mentions"] == [b["agent_id"]]
    # Unknown handle stays in text; @ remains a regular character.
    assert "@nobody" in chat["text"]


def test_chat_no_mentions_yields_empty_list(client) -> None:
    a = _ra(client)
    _jp(client, a, "cream-terrazzo")
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "no pings here"},
    )
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    assert obs["recent_chat"][-1]["mentions"] == []


def test_observe_marks_you_are_mentioned(client) -> None:
    a = _ra(client, username="Alice")
    b = _ra(client, username="Bob", color="#ff6b9d")
    _jp(client, a, "cream-terrazzo")
    _jp(client, b, "cream-terrazzo")
    cursor_resp = client.get("/api/parties/cream-terrazzo/observe").json()
    cursor = cursor_resp["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "agent", "id": a["agent_id"]},
              "text": "hey @bob"},
    )
    obs_b = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "viewer_id": b["agent_id"]},
    ).json()
    chat = [e for e in obs_b["events"] if e["type"] == "chat"][0]
    assert chat["you_are_mentioned"] is True

    obs_a = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"since": cursor, "viewer_id": a["agent_id"]},
    ).json()
    chat_a = [e for e in obs_a["events"] if e["type"] == "chat"][0]
    # The speaker themselves should not get the flag.
    assert chat_a.get("you_are_mentioned", False) is False
