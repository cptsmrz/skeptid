"""Unit tests for SQLite database store, shadow provider logging, and feedback."""

import tempfile
from pathlib import Path

import pytest

from skeptid.core.types import Evidence, Modality, Verdict
from skeptid.store.db import SkeptidDatabase


@pytest.fixture
def temp_db() -> SkeptidDatabase:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield SkeptidDatabase(db_path=db_path)


def test_record_analysis_and_shadow_logging(temp_db: SkeptidDatabase) -> None:
    verdict = Verdict(
        id="test-uuid-001",
        modality=Modality.EMAIL,
        label="phishing",
        risk=0.88,
        level="HIGH",
        confidence=0.75,
        disagreement=False,
        primary_provider="own",
        mock=False,
        providers=[
            {"id": "own", "ok": True, "risk": 0.88, "latency_ms": 15, "model_version": "text_v1"},
            {"id": "opensource", "ok": True, "risk": 0.85, "latency_ms": 250, "model_version": "p2"},
        ],
        evidence=[Evidence(kind="span", description="test", payload={})],
    )
    temp_db.record_analysis(verdict)

    stats = temp_db.get_summary_stats()
    assert stats["total_analyses"] == 1
    assert stats["agreement_rate"] == 1.0
    assert stats["fallback_count"] == 0
    assert "own" in stats["provider_stats"]
    assert stats["provider_stats"]["own"]["p50_latency_ms"] == 15


def test_record_feedback_tagged_source_demo(temp_db: SkeptidDatabase) -> None:
    rec = temp_db.record_feedback(analysis_id="test-uuid-001", correct=True, true_label="phishing")
    assert rec.source == "demo"
    assert rec.correct is True
    assert rec.analysis_id == "test-uuid-001"

    stats = temp_db.get_summary_stats()
    assert stats["total_feedback"] == 1
