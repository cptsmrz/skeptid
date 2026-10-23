"""Unit tests for OwnTextProvider (P3)."""

import pytest

from skeptid.core.types import TEXT_LABELS, AnalysisInput, Modality
from skeptid.providers.own_text import OwnTextProvider


@pytest.mark.asyncio
async def test_own_text_provider_analysis() -> None:
    provider = OwnTextProvider(model_path="models/text_v1.joblib")
    is_healthy = await provider.health()
    assert is_healthy is True

    payload = AnalysisInput(
        modality=Modality.TEXT,
        text="WINNER!! You have won a guaranteed cash prize! Call urgently to claim.",
    )
    res = await provider.analyze(payload)
    assert res.ok is True
    assert res.provider_id == "own"
    assert res.model_version == "text_v1"
    assert 0.0 <= res.risk <= 1.0

    # Verify probability distribution over all TEXT_LABELS
    assert set(res.label_scores.keys()) == set(TEXT_LABELS)
    assert abs(sum(res.label_scores.values()) - 1.0) < 0.01

    # Verify explainable evidence spans
    assert len(res.evidence) >= 1
    spans = [e for e in res.evidence if e.kind == "span"]
    assert len(spans) >= 1
    for s in spans:
        assert "start" in s.payload
        assert "end" in s.payload
        assert s.payload["start"] <= s.payload["end"]


@pytest.mark.asyncio
async def test_own_text_provider_missing_model() -> None:
    provider = OwnTextProvider(model_path="models/non_existent.joblib")
    assert await provider.health() is False

    res = await provider.analyze(AnalysisInput(modality=Modality.TEXT, text="hello"))
    assert res.ok is False
    assert res.error == "model_not_found"
