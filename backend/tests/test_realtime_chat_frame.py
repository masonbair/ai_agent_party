"""Regression: WS chat frame must include participant_id, text, at, seq.

These are the fields the frontend (useRealtimeParty + ChatBubble) reads.
Keep this test in sync with frontend expectations.
"""
from app.events import ChatEvent
from app.realtime import _serialise_event


def test_chat_event_ws_frame_has_required_fields() -> None:
    event = ChatEvent(seq=42, participant_id="abc", text="hi", at=1700000000.0)

    frame = _serialise_event(event)

    assert frame["type"] == "event"
    assert frame["cursor"] == 42
    payload = frame["event"]
    assert payload["type"] == "chat"
    assert payload["participant_id"] == "abc"
    assert payload["text"] == "hi"
    assert payload["at"] == 1700000000.0
    assert payload["seq"] == 42
