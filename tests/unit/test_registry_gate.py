"""Unit tests for registry promotion gate."""

import pytest

from skeptid.training.registry import GateRefusedError, check_gate, promote_modality_primary


def test_registry_gate_refuses_when_classes_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_registry = {
        "models": {
            "text_incomplete": {
                "modality": "text",
                "coverage": ["safe", "spam"],
                "missing_classes": ["phishing", "threat", "bullying"],
                "metrics": {"macro_f1": 0.85, "per_class": {}},
            }
        }
    }
    monkeypatch.setattr("skeptid.training.registry.load_registry", lambda: fake_registry)
    gate_met, candidate, reasons = check_gate("text", "text_incomplete")
    assert gate_met is False
    assert candidate == "text_incomplete"
    assert any("missing classes" in r.lower() or "coverage incomplete" in r.lower() for r in reasons)


def test_promote_raises_when_gate_unmet(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_registry = {
        "models": {
            "text_incomplete": {
                "modality": "text",
                "coverage": ["safe", "spam"],
                "missing_classes": ["phishing", "threat", "bullying"],
                "metrics": {"macro_f1": 0.50, "per_class": {}},
            }
        }
    }
    monkeypatch.setattr("skeptid.training.registry.load_registry", lambda: fake_registry)
    with pytest.raises(GateRefusedError) as exc_info:
        promote_modality_primary("text", "text_incomplete")
    assert "Gate refused" in str(exc_info.value)
