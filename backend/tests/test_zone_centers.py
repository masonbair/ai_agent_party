from fastapi.testclient import TestClient


def test_observe_room_zones_include_world_unit_centers(client: TestClient) -> None:
    body = client.get("/api/parties/cream-terrazzo/observe").json()
    zones = {z["id"]: z for z in body["room"]["zones"]}
    dance = zones["dance"]
    expected_cx = (6.0 + 34.0 / 2) / 100.0 * 800.0
    expected_cy = (8.0 + 36.0 / 2) / 100.0 * 500.0
    assert dance["centerX"] == expected_cx
    assert dance["centerY"] == expected_cy
    user = client.post(
        "/api/session", json={"username": "Alice", "color": "#ff6b9d"}
    ).json()
    principal = {"kind": "human", "id": user["session_id"]}
    client.post(
        "/api/parties/cream-terrazzo/join", json={"principal": principal}
    )
    moved = client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": principal, "x": dance["centerX"], "y": dance["centerY"]},
    ).json()
    assert moved["zone"] == "dance"
