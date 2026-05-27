def test_guide_documents_gestures(client):
    body = client.get("/api/agent-guide").text
    for g in ("wave", "point", "dance", "jump", "sit", "shiver", "bow", "nod"):
        assert g in body
    assert "/gesture" in body


def test_guide_documents_gesture_cooldown(client):
    body = client.get("/api/agent-guide").text
    # Mentions the burst and refill so an agent can pace itself.
    assert "burst" in body.lower()
    assert "2 second" in body or "2s" in body


def test_guide_documents_cosmetics(client):
    body = client.get("/api/agent-guide").text
    for e in ("confetti", "sparkle", "lights_flash", "ping"):
        assert e in body
    assert "/cosmetic" in body
    assert "room" in body.lower()  # mentions it's room-wide
    assert "10 second" in body or "10s" in body  # cooldown


def test_guide_documents_targeted_reactions(client):
    body = client.get("/api/agent-guide").text
    assert "target_seq" in body
    assert "target_actor_id" in body


def test_guide_documents_facing(client):
    body = client.get("/api/agent-guide").text
    assert "facing" in body
    for d in ("up", "down", "left", "right"):
        assert d in body
