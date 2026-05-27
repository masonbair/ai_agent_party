from tests.conftest import join_party, register_agent, register_human


def test_list_parties_includes_occupancy_zero_for_unvisited_party(client):
    res = client.get("/api/parties")
    assert res.status_code == 200
    body = res.json()
    assert "parties" in body and len(body["parties"]) >= 1
    for entry in body["parties"]:
        assert entry["occupancy"] == {
            "humans": 0,
            "agents": 0,
            "total": 0,
            "active_last_5min": 0,
        }


def test_list_parties_counts_mixed_population(client):
    h = register_human(client)
    a = register_agent(client, color="#4db6ac")
    join_party(client, h, slug="cream-terrazzo")
    join_party(client, a, slug="cream-terrazzo")
    res = client.get("/api/parties")
    assert res.status_code == 200
    entry = next(p for p in res.json()["parties"] if p["slug"] == "cream-terrazzo")
    occ = entry["occupancy"]
    assert occ["humans"] == 1
    assert occ["agents"] == 1
    assert occ["total"] == 2
    assert occ["active_last_5min"] == 2
