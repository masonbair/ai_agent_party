from fastapi.testclient import TestClient


def test_list_parties_includes_cream_terrazzo(client: TestClient) -> None:
    r = client.get("/api/parties")
    assert r.status_code == 200
    slugs = {p["slug"] for p in r.json()["parties"]}
    assert "cream-terrazzo" in slugs


def test_get_party_returns_full_config(client: TestClient) -> None:
    r = client.get("/api/parties/cream-terrazzo")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == "cream-terrazzo"
    assert {z["id"] for z in body["zones"]} == {"dance", "chill", "snacks"}
    assert body["music"]["url"] is None


def test_get_party_404_for_unknown_slug(client: TestClient) -> None:
    r = client.get("/api/parties/does-not-exist")
    assert r.status_code == 404
