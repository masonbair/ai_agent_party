from fastapi.testclient import TestClient

from app.events import NoteReactionEvent


def test_note_reaction_event_shape():
    ev = NoteReactionEvent(
        seq=1,
        module_id="freenotes-1",
        note_id="abc",
        emoji="🎉",
        at=1.0,
        actor_id="p",
        actor_username="alex",
        actor_kind="human",
    )
    assert ev.type == "note_reaction"
    assert ev.emoji == "🎉"


from app.events import Participant
from app.models import (
    FreeNotesModule,
    Music,
    PartyConfig,
    Room,
    Theme,
    WorldSize,
)
from app.world import PartyWorld


def _world() -> PartyWorld:
    party = PartyConfig(
        slug="t", name="t", description="t",
        theme=Theme(floor="#fff", accent="#000"),
        zones=[],
        music=Music(url=None, label="x"),
        worldSize=WorldSize(width=800, height=500),
        room=Room(border="1px solid #000", walls=[]),
        modules=[FreeNotesModule(id="freenotes-1")],
    )
    return PartyWorld(party)


def test_react_to_note_increments_and_emits_event():
    world = _world()
    world.join(Participant(id="p1", kind="human", username="alex",
                           color="#ff6b9d", x=100.0, y=100.0, joined_at=0.0))
    note_ev = world.create_note("p1", "freenotes-1", "hi", "pink", 100.0, 100.0)
    note_id = note_ev.note.id
    ev = world.react_to_note("p1", "freenotes-1", note_id, "🎉")
    assert ev.type == "note_reaction"
    assert ev.emoji == "🎉"
    # Counter updated on the note record.
    notes = world.notes_by_module["freenotes-1"]
    assert notes[0].reactions == {"🎉": 1}


def test_react_to_note_unknown_emoji_raises():
    world = _world()
    world.join(Participant(id="p1", kind="human", username="alex",
                           color="#ff6b9d", x=100.0, y=100.0, joined_at=0.0))
    note_ev = world.create_note("p1", "freenotes-1", "hi", "pink", 100.0, 100.0)
    import pytest
    from app.validation import ReactionValidationError
    with pytest.raises(ReactionValidationError):
        world.react_to_note("p1", "freenotes-1", note_ev.note.id, "💩")


def _http_join(client: TestClient, name: str, x: float, y: float) -> str:
    r = client.post("/api/session", json={"username": name, "color": "#ff6b9d"})
    sid = r.json()["session_id"]
    client.post(
        "/api/parties/cream-terrazzo/join",
        json={"principal": {"kind": "human", "id": sid}, "x": x, "y": y},
    )
    return sid


def test_react_to_note_route_succeeds(client: TestClient) -> None:
    sid = _http_join(client, "alex", x=400.0, y=250.0)
    note_resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "graf", "color": "pink", "x": 400.0, "y": 250.0,
        },
    )
    assert note_resp.status_code == 200, note_resp.json()
    note_id = note_resp.json()["note"]["id"]
    resp = client.post(
        f"/api/parties/cream-terrazzo/modules/freenotes-1/notes/{note_id}/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "🎉"},
    )
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["emoji"] == "🎉"
    assert "cursor" in body


def test_react_to_note_unknown_note_returns_404(client: TestClient) -> None:
    sid = _http_join(client, "alex", x=400.0, y=250.0)
    resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes/deadbeef/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "🎉"},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "not_found"


def test_react_to_note_invalid_emoji_returns_422(client: TestClient) -> None:
    sid = _http_join(client, "alex", x=400.0, y=250.0)
    note_resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "g", "color": "pink", "x": 400.0, "y": 250.0,
        },
    )
    assert note_resp.status_code == 200, note_resp.json()
    nid = note_resp.json()["note"]["id"]
    resp = client.post(
        f"/api/parties/cream-terrazzo/modules/freenotes-1/notes/{nid}/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "💩"},
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "invalid_emoji"


def test_reactions_appear_on_note_in_observe(client: TestClient) -> None:
    sid = _http_join(client, "alex", x=400.0, y=250.0)
    note_resp = client.post(
        "/api/parties/cream-terrazzo/modules/freenotes-1/notes",
        json={
            "principal": {"kind": "human", "id": sid},
            "text": "g", "color": "pink", "x": 400.0, "y": 250.0,
        },
    )
    nid = note_resp.json()["note"]["id"]
    client.post(
        f"/api/parties/cream-terrazzo/modules/freenotes-1/notes/{nid}/react",
        json={"principal": {"kind": "human", "id": sid}, "emoji": "🎉"},
    )
    obs = client.get(
        "/api/parties/cream-terrazzo/observe",
        params={"principal_id": sid, "principal_kind": "human"},
    )
    mods = obs.json()["modules"]
    free = next(m for m in mods if m["kind"] == "freenotes")
    note = next(n for n in free["notes"] if n["id"] == nid)
    assert note["reactions"] == {"🎉": 1}
