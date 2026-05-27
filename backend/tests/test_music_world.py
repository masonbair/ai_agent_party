from app.events import MusicChangedEvent, Event


def test_music_changed_event_has_unified_actor_fields():
    ev = MusicChangedEvent(
        seq=1,
        track_id="lofi-loop",
        playing=True,
        volume=42,
        at=12345.0,
        actor_id="agent_x",
        actor_username="DJ",
        actor_kind="agent",
        room_wide=True,
    )
    assert ev.type == "music_changed"
    assert ev.track_id == "lofi-loop"
    assert ev.playing is True
    assert ev.volume == 42
    assert ev.actor_id == "agent_x"
    assert ev.room_wide is True


def test_music_changed_event_is_in_event_union():
    # Pydantic discriminator wiring sanity-check.
    assert MusicChangedEvent in Event.__args__  # type: ignore[attr-defined]
