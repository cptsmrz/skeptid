"""Unit tests for VideoEngine frame sampling, temporal aggregation, and consistency checks."""

import os
import tempfile

import cv2  # type: ignore[import-untyped]
import numpy as np
import pytest
from fastapi import HTTPException

from skeptid.core.types import Modality
from skeptid.engines.video import VideoEngine


def create_synthetic_video_bytes(num_frames: int = 24, fps: float = 24.0, alternating: bool = False) -> bytes:
    """Helper to generate a minimal valid MP4 video in memory."""
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, fps, (64, 64))
        for i in range(num_frames):
            if alternating and i % 2 == 1:
                # High frequency random noise frame to induce variance
                frame = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
            else:
                frame = np.full((64, 64, 3), (i * 10) % 256, dtype=np.uint8)
            writer.write(frame)
        writer.release()
        with open(path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(path):
            os.remove(path)


@pytest.mark.asyncio
async def test_video_engine_uniform_sampling_and_timeline() -> None:
    engine = VideoEngine()
    video_bytes = create_synthetic_video_bytes(num_frames=30, fps=15.0)

    verdict = await engine.analyze(video_bytes, filename="test.mp4")

    assert verdict.modality == Modality.VIDEO
    assert 0.0 <= verdict.risk <= 1.0
    assert verdict.level in ["LOW", "MEDIUM", "HIGH"]
    assert 0.0 <= verdict.confidence <= 1.0

    # Verify frame timeline evidence
    timeline_ev = next((ev for ev in verdict.evidence if ev.kind == "frame_score"), None)
    assert timeline_ev is not None
    frames = timeline_ev.payload.get("frames", [])
    assert len(frames) > 0
    assert all("t" in f and "score" in f for f in frames)

    # Verify heatmap evidence for highest risk frame
    heatmap_ev = next((ev for ev in verdict.evidence if ev.kind == "heatmap"), None)
    assert heatmap_ev is not None
    assert "png_b64" in heatmap_ev.payload


@pytest.mark.asyncio
async def test_video_engine_temporal_inconsistency_flag() -> None:
    engine = VideoEngine()
    # Alternating smooth and noisy frames creates large jump between adjacent frames
    video_bytes = create_synthetic_video_bytes(num_frames=20, fps=10.0, alternating=True)

    verdict = await engine.analyze(video_bytes, filename="inconsistent.mp4")

    # High temporal variance should generate a flag evidence item
    flag_ev = next((ev for ev in verdict.evidence if ev.kind == "flag"), None)
    assert flag_ev is not None
    assert "temporal inconsistency" in flag_ev.description.lower()


@pytest.mark.asyncio
async def test_video_engine_duration_limit_enforced() -> None:
    engine = VideoEngine()
    # 70 seconds duration at 1 fps = 70 frames > 60.0s max limit
    long_video = create_synthetic_video_bytes(num_frames=70, fps=1.0)

    with pytest.raises(HTTPException) as exc_info:
        await engine.analyze(long_video, filename="toolong.mp4")

    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed limit" in str(exc_info.value.detail)
