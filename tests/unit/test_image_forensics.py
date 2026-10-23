"""Unit tests for image forensic extractors and P3 OwnImageProvider."""

import io

import numpy as np
import pytest
from PIL import Image

from skeptid.core.types import IMAGE_LABELS, AnalysisInput, Modality
from skeptid.forensics.ela import compute_ela
from skeptid.forensics.exif import analyze_exif
from skeptid.forensics.heatmap import generate_forensic_heatmap
from skeptid.forensics.noise import compute_noise_residual
from skeptid.forensics.spectrum import compute_spectrum
from skeptid.providers.own_image import OwnImageProvider


def create_synthetic_image(
    width: int = 128, height: int = 128, pattern: str = "gradient"
) -> Image.Image:
    """Helper to create synthetic in-memory test images."""
    if pattern == "gradient":
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            for x in range(width):
                arr[y, x] = [int(255 * x / width), int(255 * y / height), 128]
        return Image.fromarray(arr, mode="RGB")
    elif pattern == "noise":
        arr = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        return Image.fromarray(arr, mode="RGB")
    else:
        return Image.new("RGB", (width, height), color=(200, 200, 200))


def test_compute_ela() -> None:
    img = create_synthetic_image(128, 128, "gradient")
    res = compute_ela(img, quality=90)

    assert isinstance(res.mean_diff, float)
    assert res.mean_diff >= 0.0
    assert isinstance(res.max_diff, float)
    assert isinstance(res.block_variance, float)
    assert 0.0 <= res.high_diff_block_ratio <= 1.0
    assert res.diff_image.size == (128, 128)


def test_compute_spectrum() -> None:
    img = create_synthetic_image(128, 128, "gradient")
    res = compute_spectrum(img)

    assert 0.0 <= res.high_freq_ratio <= 1.0
    assert isinstance(res.radial_decay_slope, float)
    assert 0.0 <= res.peak_anomaly_score <= 1.0
    assert res.azimuthal_variance >= 0.0


def test_compute_noise_residual() -> None:
    img = create_synthetic_image(128, 128, "noise")
    res = compute_noise_residual(img)

    assert res.mean_variance >= 0.0
    assert isinstance(res.mean_kurtosis, float)
    assert res.channel_variance_ratio >= 1.0
    assert isinstance(res.kurtosis_anomaly, bool)
    assert res.residual_array.shape == (128, 128, 3)


def test_analyze_exif() -> None:
    img = create_synthetic_image(512, 512, "gradient")
    res = analyze_exif(img)

    assert res.has_exif is False
    assert res.has_camera_info is False
    # (512, 512) square without camera EXIF is flagged as dimension anomaly
    assert res.dimension_anomaly is True


def test_generate_forensic_heatmap() -> None:
    img = create_synthetic_image(128, 128, "gradient")
    ela = compute_ela(img)
    noise = compute_noise_residual(img)

    png_b64, max_anom = generate_forensic_heatmap(
        img,
        ela_amplified_img=ela.diff_image,
        noise_residual=noise.residual_array,
    )

    assert isinstance(png_b64, str)
    assert len(png_b64) > 50
    assert 0.0 <= max_anom <= 1.0


@pytest.mark.asyncio
async def test_own_image_provider_analyze() -> None:
    provider = OwnImageProvider(provider_id="own")
    assert await provider.health() is True

    img = create_synthetic_image(128, 128, "gradient")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    img_bytes = buf.getvalue()

    inp = AnalysisInput(modality=Modality.IMAGE, raw_bytes=img_bytes)
    res = await provider.analyze(inp)

    assert res.ok is True
    assert res.provider_id == "own"
    assert 0.0 <= res.risk <= 1.0
    assert res.coverage == IMAGE_LABELS
    assert all(lbl in res.label_scores for lbl in IMAGE_LABELS)
    assert round(sum(res.label_scores.values()), 2) == 1.00
    assert any(ev.kind == "heatmap" for ev in res.evidence)
