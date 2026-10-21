"""Unit tests for deterministic MockProvider."""

import pytest

from skeptid.core.types import AnalysisInput, Modality
from skeptid.providers.mock import MockProvider


@pytest.mark.asyncio
async def test_mock_provider_determinism() -> None:
    provider = MockProvider(provider_id="mock_test", modality=Modality.TEXT)
    inp = AnalysisInput(modality=Modality.TEXT, text="Urgent wire transfer required")

    res1 = await provider.analyze(inp)
    res2 = await provider.analyze(inp)

    assert res1.ok is True
    assert res2.ok is True
    assert res1.risk == res2.risk
    assert res1.label_scores == res2.label_scores
    assert res1.model_version == "mock"


@pytest.mark.asyncio
async def test_mock_provider_different_inputs() -> None:
    provider = MockProvider(provider_id="mock_test", modality=Modality.TEXT)
    inp1 = AnalysisInput(modality=Modality.TEXT, text="Input A")
    inp2 = AnalysisInput(modality=Modality.TEXT, text="Input B completely different")

    res1 = await provider.analyze(inp1)
    res2 = await provider.analyze(inp2)

    assert (res1.risk != res2.risk) or (res1.label_scores != res2.label_scores)


@pytest.mark.asyncio
async def test_mock_provider_error_handling() -> None:
    provider = MockProvider(provider_id="mock_test", modality=Modality.TEXT, force_error="Simulated upstream failure")
    inp = AnalysisInput(modality=Modality.TEXT, text="Hello")

    res = await provider.analyze(inp)
    assert res.ok is False
    assert res.error == "Simulated upstream failure"
    assert await provider.health() is False
