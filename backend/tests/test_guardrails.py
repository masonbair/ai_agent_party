"""Tests for backend/app/guardrails.py — content masking via blocklist."""

import pytest
from fastapi.testclient import TestClient

import app.guardrails as guardrails
from app.events import Participant
from app.store import Store


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_blocklist(monkeypatch, words: frozenset[str]) -> None:
    """Swap the module-level blocklist and regex without leaking state."""
    regex = guardrails._build_regex(words)
    monkeypatch.setattr(guardrails, "BLOCKLIST", words)
    monkeypatch.setattr(guardrails, "BLOCKLIST_REGEX", regex)


# ---------------------------------------------------------------------------
# mask_blocked — basic masking
# ---------------------------------------------------------------------------

class TestMaskBlocked:
    def test_exact_whole_word_is_masked(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["damn"]))
        masked, was = guardrails.mask_blocked("damn")
        assert masked == "****"
        assert was is True

    def test_case_insensitive_masking(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["damn"]))
        masked, was = guardrails.mask_blocked("Damn!")
        assert masked == "****!"
        assert was is True

    def test_length_preserving(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["damn"]))
        masked, _ = guardrails.mask_blocked("Damn!")
        # 4 asterisks, exclamation preserved
        assert masked == "****!"
        assert len(masked) == len("Damn!")

    def test_substring_not_masked(self, monkeypatch):
        """'classic' should survive when 'ass' is blocked."""
        _patch_blocklist(monkeypatch, frozenset(["ass"]))
        masked, was = guardrails.mask_blocked("classic")
        assert masked == "classic"
        assert was is False

    def test_multiple_hits_in_one_string(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["damn", "hell"]))
        masked, was = guardrails.mask_blocked("damn it to hell")
        assert masked == "**** it to ****"
        assert was is True

    def test_was_masked_false_when_no_match(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["damn"]))
        masked, was = guardrails.mask_blocked("hello world")
        assert masked == "hello world"
        assert was is False

    def test_was_masked_true_when_match(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["hell"]))
        _, was = guardrails.mask_blocked("what the hell")
        assert was is True

    def test_all_caps_match(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["shit"]))
        masked, was = guardrails.mask_blocked("SHIT happens")
        assert masked == "**** happens"
        assert was is True

    def test_mixed_case_in_sentence(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["crap"]))
        masked, was = guardrails.mask_blocked("What a Crap day")
        assert masked == "What a **** day"
        assert was is True

    def test_blocked_word_at_start(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["fuck"]))
        masked, was = guardrails.mask_blocked("fuck this")
        assert masked == "**** this"
        assert was is True

    def test_blocked_word_at_end(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["fuck"]))
        masked, was = guardrails.mask_blocked("oh fuck")
        assert masked == "oh ****"
        assert was is True

    def test_punctuation_adjacent_to_word(self, monkeypatch):
        """Word boundaries still match next to punctuation."""
        _patch_blocklist(monkeypatch, frozenset(["damn"]))
        masked, was = guardrails.mask_blocked("damn, it!")
        assert masked == "****, it!"
        assert was is True


# ---------------------------------------------------------------------------
# mask_blocked — empty blocklist
# ---------------------------------------------------------------------------

class TestMaskBlockedEmptyBlocklist:
    def test_returns_text_unchanged(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset())
        masked, was = guardrails.mask_blocked("shit damn hell")
        assert masked == "shit damn hell"
        assert was is False


# ---------------------------------------------------------------------------
# contains_blocked
# ---------------------------------------------------------------------------

class TestContainsBlocked:
    def test_true_for_blocked_word(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["damn"]))
        assert guardrails.contains_blocked("damn right") is True

    def test_false_for_clean_text(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["damn"]))
        assert guardrails.contains_blocked("hello world") is False

    def test_false_for_substring(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["ass"]))
        assert guardrails.contains_blocked("classic") is False

    def test_false_when_empty_blocklist(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset())
        assert guardrails.contains_blocked("shit damn hell") is False

    def test_case_insensitive(self, monkeypatch):
        _patch_blocklist(monkeypatch, frozenset(["hell"]))
        assert guardrails.contains_blocked("HELL yeah") is True


# ---------------------------------------------------------------------------
# _load_blocklist
# ---------------------------------------------------------------------------

class TestLoadBlocklist:
    def test_ignores_comment_lines(self, tmp_path):
        f = tmp_path / "bl.txt"
        f.write_text("# this is a comment\ndamn\n")
        result = guardrails._load_blocklist(f)
        assert result == frozenset(["damn"])

    def test_ignores_blank_lines(self, tmp_path):
        f = tmp_path / "bl.txt"
        f.write_text("\n\ndamn\n\n")
        result = guardrails._load_blocklist(f)
        assert result == frozenset(["damn"])

    def test_lowercases_entries(self, tmp_path):
        f = tmp_path / "bl.txt"
        f.write_text("DAMN\nHell\n")
        result = guardrails._load_blocklist(f)
        assert result == frozenset(["damn", "hell"])

    def test_trims_whitespace(self, tmp_path):
        f = tmp_path / "bl.txt"
        f.write_text("  damn  \n  hell  \n")
        result = guardrails._load_blocklist(f)
        assert result == frozenset(["damn", "hell"])

    def test_missing_file_returns_empty(self, tmp_path):
        missing = tmp_path / "nonexistent.txt"
        result = guardrails._load_blocklist(missing)
        assert result == frozenset()

    def test_empty_file_returns_empty(self, tmp_path):
        f = tmp_path / "bl.txt"
        f.write_text("")
        result = guardrails._load_blocklist(f)
        assert result == frozenset()

    def test_only_comments_returns_empty(self, tmp_path):
        f = tmp_path / "bl.txt"
        f.write_text("# comment 1\n# comment 2\n")
        result = guardrails._load_blocklist(f)
        assert result == frozenset()


# ---------------------------------------------------------------------------
# Integration — masking flows through chat, DM, and sticky-note validators
# ---------------------------------------------------------------------------

SLUG = "cream-terrazzo"


def _join_party(store: Store, session_id: str, username: str) -> None:
    world = store.get_or_create_world(SLUG)
    assert world is not None
    world.join(
        Participant(
            id=session_id,
            kind="human",
            username=username,
            color="#ff6b9d",
            x=100.0,
            y=100.0,
            joined_at=0.0,
        )
    )


class TestIntegration:
    """Verify that blocked words are masked in chat, DMs, and sticky notes."""

    # ------------------------------------------------------------------
    # Chat masking
    # ------------------------------------------------------------------

    def test_chat_response_contains_masked_text(self, client: TestClient, store: Store) -> None:
        """POST /chat with a blocked word: the observe snapshot shows the masked form."""
        sid = store.create_session(username="Alice", color="#ff6b9d").session_id
        _join_party(store, sid, "Alice")
        principal = {"kind": "human", "id": sid}

        # Capture cursor before the chat
        cur = client.get(f"/api/parties/{SLUG}/observe").json()["cursor"]

        # Send a message with a blocked word
        r = client.post(
            f"/api/parties/{SLUG}/chat",
            json={"principal": principal, "text": "what the damn thing"},
        )
        assert r.status_code == 200

        # The observe diff should show the masked form in the broadcast event
        diff = client.get(f"/api/parties/{SLUG}/observe?since={cur}").json()
        chat_events = [e for e in diff["events"] if e["type"] == "chat"]
        assert len(chat_events) == 1
        assert chat_events[0]["text"] == "what the **** thing"

    def test_chat_observe_snapshot_contains_masked_text(self, client: TestClient, store: Store) -> None:
        """The recent_chat snapshot on the initial observe also shows the masked text."""
        sid = store.create_session(username="Alice", color="#ff6b9d").session_id
        _join_party(store, sid, "Alice")
        principal = {"kind": "human", "id": sid}

        client.post(
            f"/api/parties/{SLUG}/chat",
            json={"principal": principal, "text": "damn it"},
        )

        obs = client.get(f"/api/parties/{SLUG}/observe").json()
        texts = [c["text"] for c in obs["recent_chat"]]
        assert "**** it" in texts

    # ------------------------------------------------------------------
    # DM masking
    # ------------------------------------------------------------------

    def test_dm_stored_text_is_masked(self, client: TestClient, store: Store) -> None:
        """POST /dm/send with a blocked word: the thread history stores the masked form."""
        alice = store.create_session(username="Alice", color="#ff6b9d")
        bob = store.create_session(username="Bob", color="#9c27b0")
        _join_party(store, alice.session_id, "Alice")
        _join_party(store, bob.session_id, "Bob")

        a, b = alice.session_id, bob.session_id

        r = client.post(
            "/api/dm/send",
            json={
                "principal": {"kind": "human", "id": a},
                "recipient": {"kind": "human", "id": b},
                "text": "damn right",
            },
        )
        assert r.status_code == 200

        tk = f"human:{min(a, b)}|human:{max(a, b)}"
        history = client.get(
            f"/api/dm/threads/{tk}/history",
            params={"principal_kind": "human", "principal_id": a},
        ).json()
        assert history["messages"][0]["text"] == "**** right"

    def test_dm_thread_list_shows_masked_last_text(self, client: TestClient, store: Store) -> None:
        """The thread list last_text field also reflects the masked form."""
        alice = store.create_session(username="Alice", color="#ff6b9d")
        bob = store.create_session(username="Bob", color="#9c27b0")
        _join_party(store, alice.session_id, "Alice")
        _join_party(store, bob.session_id, "Bob")

        a, b = alice.session_id, bob.session_id

        client.post(
            "/api/dm/send",
            json={
                "principal": {"kind": "human", "id": a},
                "recipient": {"kind": "human", "id": b},
                "text": "what the damn",
            },
        )

        threads = client.get(
            "/api/dm/threads",
            params={"principal_kind": "human", "principal_id": a},
        ).json()["threads"]
        assert threads[0]["last_text"] == "what the ****"

    # ------------------------------------------------------------------
    # Sticky-note masking
    # ------------------------------------------------------------------

    def test_note_create_stores_masked_text(self, client: TestClient, store: Store) -> None:
        """Creating a sticky note with a blocked word stores the masked form."""
        sid = store.create_session(username="alice", color="#ff6b9d").session_id
        # Position near sticky-1 zone (x=110, y=445 is within interaction range)
        world = store.get_or_create_world(SLUG)
        assert world is not None
        world.join(
            Participant(
                id=sid,
                kind="human",
                username="alice",
                color="#ff6b9d",
                x=110.0,
                y=445.0,
                joined_at=0.0,
            )
        )

        r = client.post(
            f"/api/parties/{SLUG}/modules/sticky-1/notes",
            json={
                "principal": {"kind": "human", "id": sid},
                "text": "damn good idea",
                "color": "yellow",
                "x": 5,
                "y": 5,
            },
        )
        assert r.status_code == 200, r.text
        note = r.json()["note"]
        assert note["text"] == "**** good idea"

    def test_note_update_stores_masked_text(self, client: TestClient, store: Store) -> None:
        """Updating a sticky note with a blocked word stores the masked form."""
        sid = store.create_session(username="alice", color="#ff6b9d").session_id
        world = store.get_or_create_world(SLUG)
        assert world is not None
        world.join(
            Participant(
                id=sid,
                kind="human",
                username="alice",
                color="#ff6b9d",
                x=110.0,
                y=445.0,
                joined_at=0.0,
            )
        )

        # Create a clean note first
        r = client.post(
            f"/api/parties/{SLUG}/modules/sticky-1/notes",
            json={
                "principal": {"kind": "human", "id": sid},
                "text": "clean text",
                "color": "yellow",
                "x": 5,
                "y": 5,
            },
        )
        assert r.status_code == 200, r.text
        note_id = r.json()["note"]["id"]

        # Update the note with a blocked word
        r2 = client.patch(
            f"/api/parties/{SLUG}/modules/sticky-1/notes/{note_id}",
            json={
                "principal": {"kind": "human", "id": sid},
                "text": "damn update",
            },
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["note"]["text"] == "**** update"
