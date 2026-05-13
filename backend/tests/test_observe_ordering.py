from fastapi.testclient import TestClient


def _human(client: TestClient) -> dict:
    return client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()


def _principal(user: dict) -> dict:
    return {"kind": "human", "id": user["session_id"]}


def test_observe_events_sorted_ascending_by_seq(client: TestClient) -> None:
    user = _human(client)
    cursor = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": _principal(user)},
    ).json()["cursor"]

    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal(user), "x": 200, "y": 100},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal(user), "text": "hello"},
    )
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": _principal(user), "x": 250, "y": 120},
    )
    client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": _principal(user), "text": "bye"},
    )

    events = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()["events"]

    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs), f"events not sorted by seq: {seqs}"
