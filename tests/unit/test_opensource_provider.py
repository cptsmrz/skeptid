"""Unit tests for OpenSourceTextProvider (P2)."""

import pytest

from skeptid.core.types import AnalysisInput, Modality
from skeptid.providers.opensource import OpenSourceTextProvider


@pytest.mark.asyncio
async def test_opensource_text_provider_graceful_fallback() -> None:
    provider = OpenSourceTextProvider()
    payload = AnalysisInput(modality=Modality.TEXT, text="Sample text analysis")
    res = await provider.analyze(payload)

    # In environments where optional detoxify/transformers are not installed,
    # it must return ok=False with clean error code and not raise an unhandled exception.
    if not res.ok:
        assert res.error == "optional_dependency_not_installed"
        assert res.provider_id == "opensource"
    else:
        assert res.risk >= 0.0
        assert "safe" in res.label_scores
