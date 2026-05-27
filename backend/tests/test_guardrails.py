"""Tests for backend/app/guardrails.py — content masking via blocklist."""

import importlib
import sys
from pathlib import Path

import pytest

import app.guardrails as guardrails


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
