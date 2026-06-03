def _assert_envelope(body, expected_code):
    detail = body.get("detail")
    assert isinstance(detail, dict), detail
    assert detail.get("error") == expected_code, detail
    assert isinstance(detail.get("message"), str), detail


def test_unknown_route_returns_envelope(client):
    resp = client.get("/api/no-such-endpoint")
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "not_found")


def test_wrong_method_returns_envelope(client):
    # /api/health is GET-only
    resp = client.post("/api/health")
    assert resp.status_code == 405
    _assert_envelope(resp.json(), "method_not_allowed")
