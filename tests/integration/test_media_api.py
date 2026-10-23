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


def test_analyze_media_video_frame_scores_timeline_and_providers(client: TestClient) -> None:
    """Requirement: Video verdict must include a frame_score evidence entry per sampled

    frame (time in seconds, score) plus peak-frame heatmap, and at least two providers.
    """
    # 24 frames at 12 fps = 2.0s duration; samples min(16, 24) = 16 frames (>= 8)
    mp4_bytes = create_synthetic_video_bytes(num_frames=24, fps=12.0)
    files = {"file": ("real_sample.mp4", mp4_bytes, "video/mp4")}

    resp = client.post("/api/media/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()

    # 1. Assert at least 8 frame_score entries
    frame_score_evs = [ev for ev in data["evidence"] if ev["kind"] == "frame_score"]
    assert len(frame_score_evs) >= 8, (
        f"Expected >= 8 frame_score entries, got {len(frame_score_evs)}"
    )
    for ev in frame_score_evs:
        payload = ev["payload"]
        assert "t" in payload, "Missing timestamp in frame_score payload"
        assert "score" in payload, "Missing score in frame_score payload"
        assert isinstance(payload["t"], (int, float))
        assert isinstance(payload["score"], (int, float))
        assert 0.0 <= payload["score"] <= 1.0

    # 2. Assert peak-frame heatmap evidence exists
    heatmap_evs = [ev for ev in data["evidence"] if ev["kind"] == "heatmap"]
    assert len(heatmap_evs) >= 1, "Expected peak-frame heatmap evidence"
    heatmap_payload = heatmap_evs[0]["payload"]
    assert "png_b64" in heatmap_payload
    assert len(heatmap_payload["png_b64"]) > 50

    # 3. Assert at least two providers shown
    providers = data["providers"]
    assert len(providers) >= 2, f"Expected at least two providers, got {len(providers)}"
    provider_ids = [p["id"] for p in providers]
    assert "own" in provider_ids
    assert "opensource" in provider_ids

    # 4. Assert external_used is False when external provider is mock/not used
    assert data["external_used"] is False


def test_analyze_media_unsupported_format(client: TestClient) -> None:
    files = {"file": ("notes.txt", b"Plain text content not an image", "text/plain")}
    resp = client.post("/api/media/analyze", files=files)
    assert resp.status_code == 400
    assert "Unsupported media format" in resp.json()["detail"]


def test_analyze_media_missing_file(client: TestClient) -> None:
    resp = client.post("/api/media/analyze", data={"other": "value"})
    assert resp.status_code in [400, 415]
