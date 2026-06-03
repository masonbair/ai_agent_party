"""Tests for the suggested_openers pure helper (Task 4)."""

from app.onboarding import suggested_openers


def _chat(actor_id, username, text, at=0.0):
    return {
        "type": "chat",
        "actor_id": actor_id,
        "actor_username": username,
        "actor_kind": "agent",
        "text": text,
        "at": at,
    }


def _p(pid, username, joined_at=0.0):
    return {
        "id": pid,
        "username": username,
        "kind": "agent",
        "joined_at": joined_at,
    }


def test_no_chat_returns_two_with_ambience():
    out = suggested_openers(
        recent_chat=[],
        nearby_participants=[_p("p1", "Alice", joined_at=10)],
        room_summary={"music": "Lo-fi beats", "lighting": "day"},
    )
    assert len(out) == 2
    assert any("@Alice" in s for s in out)
    assert any("music" in s.lower() or "lighting" in s.lower() or "room" in s.lower() for s in out)


def test_chat_and_nearby_returns_three():
    out = suggested_openers(
        recent_chat=[_chat("p1", "Alice", "anyone up for chess?", at=5)],
        nearby_participants=[_p("p1", "Alice", joined_at=1)],
        room_summary={"music": "", "lighting": "day"},
    )
    assert len(out) == 3
    assert out[0].startswith("Acknowledge the last topic:")
    assert "'anyone up for chess?'" in out[0]
    assert any(s == "Greet @Alice" for s in out)


def test_truncates_long_chat_at_word_boundary():
    long_text = "we were just talking about how the lighting in here is incredibly atmospheric tonight"
    out = suggested_openers(
        recent_chat=[_chat("p1", "Alice", long_text)],
        nearby_participants=[],
        room_summary={"music": "", "lighting": "day"},
    )
    ack = out[0]
    quoted = ack.split("'", 1)[1].rsplit("'", 1)[0]
    assert len(quoted) <= 41  # 40 chars + possible ellipsis
    assert quoted.endswith("...")


def test_prefers_recently_chatty_nearby_for_greeting():
    out = suggested_openers(
        recent_chat=[
            _chat("p1", "Alice", "hello", at=1),
            _chat("p2", "Bob", "hi", at=2),
        ],
        nearby_participants=[
            _p("p1", "Alice", joined_at=100),
            _p("p2", "Bob", joined_at=1),
        ],
        room_summary={"music": "", "lighting": "day"},
    )
    # Bob spoke most recently of those nearby -> Greet @Bob
    assert "Greet @Bob" in out


def test_party_lighting_used_when_no_music():
    out = suggested_openers(
        recent_chat=[],
        nearby_participants=[],
        room_summary={"music": "Music coming soon.", "lighting": "party"},
    )
    assert any("party lighting" in s for s in out)


def test_fallback_room_comment():
    out = suggested_openers(
        recent_chat=[],
        nearby_participants=[],
        room_summary={"music": "Music coming soon.", "lighting": "day"},
    )
    assert "Comment on the room" in out
