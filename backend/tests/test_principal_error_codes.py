from fastapi.testclient import TestClient

from app.errors import NOT_IN_PARTY, PRINCIPAL_UNKNOWN


def test_unknown_principal_returns_principal_unknown_code(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={
            "principal": {"kind": "agent", "id": "does-not-exist"},
            "x": 100,
            "y": 100,
        },
    )
    assert r.status_code == 401
    assert r.json() == {"detail": PRINCIPAL_UNKNOWN}


def test_session_deleted_after_action_returns_principal_unknown(client: TestClient) -> None:
    user = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "human", "id": user["session_id"]}
    client.post(
        "/api/parties/cream-terrazzo/join", json={"principal": principal}
    )
    client.delete(f"/api/session/{user['session_id']}")
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": principal, "x": 100, "y": 100},
    )
    assert r.status_code == 401
    assert r.json() == {"detail": PRINCIPAL_UNKNOWN}


def test_joined_then_left_returns_not_in_party(client: TestClient) -> None:
    user = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "human", "id": user["session_id"]}
    client.post(
        "/api/parties/cream-terrazzo/join", json={"principal": principal}
    )
    client.post(
        "/api/parties/cream-terrazzo/leave", json={"principal": principal}
    )
    r = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": principal, "x": 100, "y": 100},
    )
    assert r.status_code == 409
    assert r.json() == {"detail": NOT_IN_PARTY}
