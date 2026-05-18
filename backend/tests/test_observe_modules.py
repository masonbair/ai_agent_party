from fastapi.testclient import TestClient


def test_observe_initial_includes_modules_and_lighting(client: TestClient) -> None:
    r = client.get("/api/parties/cream-terrazzo/observe")
    assert r.status_code == 200
    body = r.json()
    assert "modules" in body["room"]
    assert "lighting" in body
    assert "active_reactions" in body
