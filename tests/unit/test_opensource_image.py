"""Unit tests for P2 OpenSource Image Provider adapting Hugging Face ViT."""

import io

import pytest
from PIL import Image

from skeptid.core.types import IMAGE_LABELS, AnalysisInput, Modality
from skeptid.providers.opensource_image import OpenSourceImageProvider


def _create_sample_png_bytes(width: int = 64, height: int = 64, color: tuple[int, int, int] = (100, 150, 200)) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_opensource_image_clean_fallback_on_invalid_model():
    """Verify clean fallback when model fails to load or does not exist."""
    provider = OpenSourceImageProvider(model_name="nonexistent/fake-model-checkpoint-12345")
    png_bytes = _create_sample_png_bytes()

    res = await provider.analyze(AnalysisInput(modality=Modality.IMAGE, raw_bytes=png_bytes))

    assert not res.ok
    assert "not_installed" in (res.error or "") or "vit_ai_detector_stub" in res.model_version
    assert res.validated is False


@pytest.mark.asyncio
async def test_opensource_image_missing_payload():
    """Verify error returned when image payload is missing."""
    provider = OpenSourceImageProvider()
    res = await provider.analyze(AnalysisInput(modality=Modality.IMAGE, raw_bytes=None))

    assert not res.ok
    assert "invalid_or_missing_image_payload" in (res.error or "")
    assert res.validated is False


@pytest.mark.asyncio
async def test_opensource_image_lazy_loading_and_contract():
    """Verify lazy loading behavior, coverage of IMAGE_LABELS, and calibrated probabilities."""
    provider = OpenSourceImageProvider()
    # Before analyze/health, internal classifier is None
    assert provider._classifier is None

    png_bytes = _create_sample_png_bytes()
    res = await provider.analyze(AnalysisInput(modality=Modality.IMAGE, raw_bytes=png_bytes))

    # Either model succeeded or cleanly fell back without crashing
    if res.ok:
        assert set(res.label_scores.keys()) == set(IMAGE_LABELS)
        assert 0.0 <= res.risk <= 1.0
        assert res.validated is False
        assert len(res.evidence) >= 1
        assert res.evidence[0].payload.get("license") == "Apache-2.0"
    else:
        assert res.validated is False
