"""Integration tests for POST /api/media/analyze endpoint."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from skeptid.core.types import IMAGE_LABELS
from skeptid.main import create_app
from tests.unit.test_video_sampling import create_synthetic_video_bytes


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def create_test_image_bytes(format_name: str = "JPEG") -> bytes:
    """Generate in-memory test image bytes."""
    img = Image.new("RGB", (100, 100), color=(128, 64, 200))
    buf = io.BytesIO()
    img.save(buf, format=format_name)
    return buf.getvalue()


def test_analyze_media_image_jpeg(client: TestClient) -> None:
    jpeg_bytes = create_test_image_bytes("JPEG")
    files = {"file": ("test.jpg", jpeg_bytes, "image/jpeg")}

    resp = client.post("/api/media/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()

    assert data["modality"] == "image"
    assert data["label"] in IMAGE_LABELS
    assert 0.0 <= data["risk"] <= 1.0
    assert data["level"] in ["LOW", "MEDIUM", "HIGH"]
    assert 0.0 <= data["confidence"] <= 1.0
    assert data["limits_note"] == "Risk score with evidence, not proof."

    # Evidence must contain heatmap
    assert any(ev["kind"] == "heatmap" for ev in data["evidence"])


def test_analyze_media_image_png(client: TestClient) -> None:
    png_bytes = create_test_image_bytes("PNG")
    files = {"file": ("sample.png", png_bytes, "image/png")}

    resp = client.post("/api/media/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["modality"] == "image"
    assert data["label"] in IMAGE_LABELS


def test_analyze_media_video_mp4(client: TestClient) -> None:
    mp4_bytes = create_synthetic_video_bytes(num_frames=20, fps=10.0)
    files = {"file": ("clip.mp4", mp4_bytes, "video/mp4")}

    resp = client.post("/api/media/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()

    assert data["modality"] == "video"
    assert 0.0 <= data["risk"] <= 1.0
    assert data["level"] in ["LOW", "MEDIUM", "HIGH"]

    # Must contain both frame_score timeline and heatmap
    kinds = [ev["kind"] for ev in data["evidence"]]
    assert "frame_score" in kinds
    assert "heatmap" in kinds


def test_analyze_media_unsupported_format(client: TestClient) -> None:
    files = {"file": ("notes.txt", b"Plain text content not an image", "text/plain")}
    resp = client.post("/api/media/analyze", files=files)
    assert resp.status_code == 400
    assert "Unsupported media format" in resp.json()["detail"]


def test_analyze_media_missing_file(client: TestClient) -> None:
    resp = client.post("/api/media/analyze", data={"other": "value"})
    assert resp.status_code in [400, 415]
