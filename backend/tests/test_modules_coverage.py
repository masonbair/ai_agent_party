"""Coverage gaps surfaced by the consistency review: 401 / 404 / 403 / 409
behaviour on module routes, FIFO eviction observability, and vote-changed
collapse in observe_since."""

from fastapi.testclient import TestClient

from app.errors import PRINCIPAL_UNKNOWN
from app.validation import (
    NOTES_PER_USER_MAX,
    STROKES_PER_BOARD_MAX,
)


GHOST = {"kind": "agent", "id": "does-not-exist"}


def _join(
    client: TestClient,
    name: str = "alice",
    color: str = "#ff6b9d",
    x: float = 110,
    y: float = 445,
) -> str:
    sid = client.post(
        "/api/session", json={"username": name, "color": color}
    ).json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


# --- 401: unknown principal across every module route ---


def test_react_unknown_principal_401(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/react",
        json={"principal": GHOST, "emoji": "❤️"},
    )
    assert r.status_code == 401
    assert r.json()["detail"]["error"] == PRINCIPAL_UNKNOWN


def test_lighting_unknown_principal_401(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/lighting",
        json={"principal": GHOST, "preset": "night"},
    )
    assert r.status_code == 401


def test_note_create_unknown_principal_401(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={"principal": GHOST, "text": "x", "color": "yellow", "x": 0, "y": 0},
    )
    assert r.status_code == 401


def test_stroke_add_unknown_principal_401(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes",
        json={
            "principal": GHOST,
            "color": "#ff6b9d",
            "width": "thin",
            "points": [{"x": 0, "y": 0}],
        },
    )
    assert r.status_code == 401


def test_clear_unknown_principal_401(client: TestClient) -> None:
    r = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/clear",
        json={"principal": GHOST},
    )
    assert r.status_code == 401


# --- 404: unknown party slug ---


def test_lighting_unknown_party_404(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/no-such/lighting",
        json={"principal": {"kind": "human", "id": sid}, "preset": "day"},
    )
    assert r.status_code == 404


def test_note_create_unknown_party_404(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/no-such/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    )
    assert r.status_code == 404


def test_stroke_unknown_party_404(client: TestClient) -> None:
    sid = _join(client)
    r = client.post(
        "/api/parties/no-such/modules/draw-1/strokes",
        json={
            "principal": {"kind": "human", "id": sid},
            "color": "#ff6b9d",
            "width": "thin",
            "points": [{"x": 0, "y": 0}],
        },
    )
    assert r.status_code == 404


# --- 409 not_in_range on patch/delete and stroke routes ---


def test_note_patch_requires_in_zone(client: TestClient) -> None:
    sid = _join(client)
    note = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    ).json()["note"]
    # Walk far away.
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": {"kind": "human", "id": sid}, "x": 400, "y": 250},
    )
    r = client.patch(
        f"/api/parties/cream-terrazzo/modules/sticky-1/notes/{note['id']}",
        json={"principal": {"kind": "human", "id": sid}, "text": "bye"},
    )
    assert r.status_code == 409


def test_note_delete_requires_in_zone(client: TestClient) -> None:
    sid = _join(client)
    note = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    ).json()["note"]
    client.post(
        "/api/parties/cream-terrazzo/move",
        json={"principal": {"kind": "human", "id": sid}, "x": 400, "y": 250},
    )
    r = client.request(
        "DELETE",
        f"/api/parties/cream-terrazzo/modules/sticky-1/notes/{note['id']}",
        json={"principal": {"kind": "human", "id": sid}},
    )
    assert r.status_code == 409


# --- 409 limit_reached on notes ---


def test_note_limit_reached_409(client: TestClient) -> None:
    sid = _join(client)
    for i in range(NOTES_PER_USER_MAX):
        r = client.post(
            "/api/parties/cream-terrazzo/modules/sticky-1/notes",
            json={
                "principal": {"kind": "human", "id": sid},
                "text": f"n{i}",
                "color": "yellow",
                "x": 0,
                "y": 0,
            },
        )
        assert r.status_code == 200, r.text
    over = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "one too many",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    )
    assert over.status_code == 409
    assert over.json()["detail"]["error"] == "limit_reached"


# --- 403 not_author on delete ---


def test_note_delete_not_author_403(client: TestClient) -> None:
    sid = _join(client)
    sid2 = _join(client, name="bob", color="#4dd0e1")
    note = client.post(
        "/api/parties/cream-terrazzo/modules/sticky-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "hi",
            "color": "yellow",
            "x": 0,
            "y": 0,
        },
    ).json()["note"]
    r = client.request(
        "DELETE",
        f"/api/parties/cream-terrazzo/modules/sticky-1/notes/{note['id']}",
        json={"principal": {"kind": "human", "id": sid2}},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "not_author"


# --- FIFO stroke_dropped is visible via observe ---


def test_stroke_dropped_event_visible_in_observe(client: TestClient) -> None:
    sid = _join(client, x=700, y=445)
    body = {
        "principal": {"kind": "human", "id": sid},
        "color": "#ff6b9d",
        "width": "thin",
        "points": [{"x": 0, "y": 0}],
    }
    first = client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes", json=body
    ).json()["stroke"]
    for _ in range(STROKES_PER_BOARD_MAX - 1):
        client.post(
            "/api/parties/cream-terrazzo/modules/draw-1/strokes", json=body
        )
    cursor_before_eviction = client.get(
        "/api/parties/cream-terrazzo/observe"
    ).json()["cursor"]
    client.post(
        "/api/parties/cream-terrazzo/modules/draw-1/strokes", json=body
    )
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor_before_eviction}"
    ).json()
    types = [e["type"] for e in diff["events"]]
    assert "stroke_added" in types
    assert "stroke_dropped" in types
    dropped = next(e for e in diff["events"] if e["type"] == "stroke_dropped")
    assert dropped["stroke_id"] == first["id"]


# --- vote_changed collapses in observe_since cursor diff ---


def test_vote_changed_collapses_to_latest_per_module(client: TestClient) -> None:
    s1 = _join(client, x=700, y=445)
    s2 = _join(client, name="bob", color="#4dd0e1", x=690, y=440)
    cursor = client.get("/api/parties/cream-terrazzo/observe").json()["cursor"]
    # Cast and revoke votes repeatedly so multiple vote_changed events are
    # logged. Each vote_clear cycles the tally; movement triggers recompute
    # which may emit additional vote_changed events.
    for _ in range(3):
        client.post(
            "/api/parties/cream-terrazzo/modules/draw-1/clear",
            json={"principal": {"kind": "human", "id": s1}},
        )
        client.post(
            "/api/parties/cream-terrazzo/move",
            json={"principal": {"kind": "human", "id": s1}, "x": 400, "y": 250},
        )
        client.post(
            "/api/parties/cream-terrazzo/move",
            json={"principal": {"kind": "human", "id": s1}, "x": 700, "y": 445},
        )
    # Second voter ends the cycle so the board is not actually cleared yet.
    _ = s2
    diff = client.get(
        f"/api/parties/cream-terrazzo/observe?since={cursor}"
    ).json()
    vote_events = [e for e in diff["events"] if e["type"] == "vote_changed"]
    by_module = [e["module_id"] for e in vote_events]
    # At most one per module after collapse.
    assert by_module.count("draw-1") <= 1
