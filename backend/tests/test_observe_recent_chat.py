from fastapi.testclient import TestClient

from app.validation import RECENT_CHAT_LIMIT


def _join(client: TestClient, name: str = "Alice", color: str = "#ff6b9d") -> str:
    r = client.post("/api/session", json={"username": name, "color": color})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}},
    )
    return sid


def test_initial_observe_includes_recent_chat(client: TestClient) -> None:
    sid = _join(client)
    for i in range(3):
        client.post(
            "/api/parties/cream-terrazzo/chat",
            json={"principal": {"kind": "human", "id": sid}, "text": f"hello {i}"},
        )
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    assert "recent_chat" in obs
    texts = [c["text"] for c in obs["recent_chat"]]
    assert texts == ["hello 0", "hello 1", "hello 2"]
    for c in obs["recent_chat"]:
        assert c["actor_username"] == "Alice"
        assert c["actor_kind"] == "human"


def test_initial_observe_recent_chat_capped_at_20(client: TestClient) -> None:
    sid = _join(client)
    for i in range(25):
        client.post(
            "/api/parties/cream-terrazzo/chat",
            json={"principal": {"kind": "human", "id": sid}, "text": f"msg{i}"},
        )
    obs = client.get("/api/parties/cream-terrazzo/observe").json()
    assert len(obs["recent_chat"]) == RECENT_CHAT_LIMIT
    assert obs["recent_chat"][-1]["text"] == "msg24"
    assert obs["recent_chat"][0]["text"] == "msg5"


def test_observe_diff_does_not_include_recent_chat(client: TestClient) -> None:
    sid = _join(client)
    cur = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": {"kind": "human", "id": sid}, "text": "hi"},
    )
    diff = client.get(f"/api/parties/cream-terrazzo/observe?since={cur}").json()
    assert "recent_chat" not in diff
