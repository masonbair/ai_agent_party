from fastapi.testclient import TestClient


def test_cream_terrazzo_seeds_freenotes_module(client: TestClient) -> None:
    resp = client.get("/api/parties/cream-terrazzo/observe")
    assert resp.status_code == 200
    mods = resp.json()["modules"]
    kinds = {m["kind"] for m in mods}
    assert "freenotes" in kinds
    free = next(m for m in mods if m["kind"] == "freenotes")
    assert free["id"] == "freenotes-1"
    # Freenotes has no interactionRect (notes are world-wide).
    assert "interactionRect" not in free
    assert free["notes"] == []
