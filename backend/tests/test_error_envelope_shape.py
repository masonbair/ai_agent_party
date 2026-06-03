"""Every API error body MUST look like:

    {"detail": {"error": "<snake_case_code>", "message": "<sentence>",
                ...optional extras}}

This test stitches together one example per error code in the codebase
and asserts the contract.
"""
from tests.conftest import register_human


def _assert_envelope(body, expected_code):
    assert isinstance(body, dict), body
    detail = body.get("detail")
    assert isinstance(detail, dict), f"detail not a dict: {detail!r}"
    assert detail.get("error") == expected_code, detail
    assert isinstance(detail.get("message"), str) and detail["message"], detail


def test_principal_unknown_is_envelope(client):
    resp = client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": "does-not-exist"}},
    )
    assert resp.status_code == 401
    _assert_envelope(resp.json(), "principal_unknown")


def test_not_in_party_chat_is_envelope(client):
    sess = register_human(client, username="Alice")
    # No join — chat should be 409 not_in_party
    resp = client.post(
        "/api/parties/cream-terrazzo/chat",
        json={"principal": sess["principal"], "text": "hi"},
    )
    assert resp.status_code == 409
    _assert_envelope(resp.json(), "not_in_party")


def test_party_not_found_is_envelope(client):
    sess = register_human(client, username="Alice")
    resp = client.post(
        "/api/parties/no-such-party/join",
        json={"principal": sess["principal"]},
    )
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "party_not_found")


def test_self_dm_is_envelope(client):
    sess = register_human(client, username="Alice")
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": sess["principal"],
            "recipient": {
                "kind": sess["principal"]["kind"],
                "id": sess["principal"]["id"],
            },
            "text": "to self",
        },
    )
    # Whatever the status is, the body must be the envelope shape.
    assert resp.status_code >= 400
    _assert_envelope(resp.json(), "self_dm")


def test_recipient_unknown_is_envelope(client):
    sess = register_human(client, username="Alice")
    resp = client.post(
        "/api/dm/send",
        json={
            "principal": sess["principal"],
            "recipient": {"kind": "human", "id": "no-such-recipient"},
            "text": "hi",
        },
    )
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "recipient_unknown")


def test_session_not_found_is_envelope(client):
    resp = client.get("/api/session/no-such-session")
    assert resp.status_code == 404
    _assert_envelope(resp.json(), "session_not_found")
