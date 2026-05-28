from app.errors import not_in_range_envelope


def test_not_in_range_envelope_contains_rect_and_actor_position():
    body = not_in_range_envelope(
        module_id="sticky-1",
        interaction_rect={"x": -24.0, "y": 396.0, "w": 228.0, "h": 128.0},
        actor_position={"x": 400.0, "y": 250.0},
    )
    assert body == {
        "error": "not_in_range",
        "message": "You are not within the module's interaction zone.",
        "module_id": "sticky-1",
        "interactionRect": {"x": -24.0, "y": 396.0, "w": 228.0, "h": 128.0},
        "actor_position": {"x": 400.0, "y": 250.0},
    }
