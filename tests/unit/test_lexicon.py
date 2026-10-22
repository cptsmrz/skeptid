"""Unit tests for forensics/lexicon.py scanner."""

from skeptid.forensics.lexicon import scan_lexicon


def test_lexicon_scans_urgency() -> None:
    text = "Please act now within 24 hours to secure your profile."
    hits = scan_lexicon(text)
    categories = [h.category for h in hits]
    assert "urgency" in categories
    assert any(h.start >= 0 and h.end > h.start for h in hits)


def test_lexicon_scans_credentials() -> None:
    text = "Click here to log in and verify your password."
    hits = scan_lexicon(text)
    categories = [h.category for h in hits]
    assert "credentials" in categories


def test_lexicon_scans_threat_and_bullying() -> None:
    text = "I will destroy you, you pathetic idiot."
    hits = scan_lexicon(text)
    categories = [h.category for h in hits]
    assert "threat" in categories
    assert "bullying" in categories


def test_lexicon_empty_text() -> None:
    assert scan_lexicon("") == []
    assert scan_lexicon("Hello world, hope you have a wonderful day.") == []
