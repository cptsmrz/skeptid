"""Unit tests for video temporal landmark & motion jitter forensics."""

import cv2
import numpy as np
import pytest
from PIL import Image

from skeptid.forensics.video_motion import (
    VideoTemporalJitterResult,
    analyze_video_temporal_jitter,
)


def test_video_motion_static_and_smooth_motion() -> None:
    # 1. Edge case: single frame
    single_frame = [np.zeros((100, 100), dtype=np.uint8)]
    res_single = analyze_video_temporal_jitter(single_frame)
    assert res_single.jitter_anomaly_score == 0.0

    # 2. Sequence of frames with smooth translation
    frames: list[np.ndarray] = []
    for step in range(6):
        img = np.zeros((360, 360), dtype=np.uint8)
        # Draw textured circle moving smoothly to the right
        cv2.circle(img, (100 + step * 5, 180), 40, 255, -1)
        cv2.circle(img, (100 + step * 5, 180), 20, 128, -1)
        frames.append(img)

    res = analyze_video_temporal_jitter(frames)
    assert isinstance(res, VideoTemporalJitterResult)
    assert res.mean_motion_jitter >= 0.0
    assert res.metadata["frames_analyzed"] == 6
    assert "tracked_points_sum" in res.metadata


def test_video_motion_jittery_deepfake_simulation() -> None:
    # Sequence with turbulent jitter (simulating face-swap flicker)
    frames: list[np.ndarray] = []
    rng = np.random.RandomState(42)
    for step in range(8):
        img = np.zeros((360, 360), dtype=np.uint8)
        # Large random jump every frame
        jitter_x = int(rng.randint(-15, 15))
        jitter_y = int(rng.randint(-15, 15))
        cv2.rectangle(img, (120 + jitter_x, 120 + jitter_y), (220 + jitter_x, 220 + jitter_y), 255, -1)
        cv2.circle(img, (170 + jitter_x, 170 + jitter_y), 15, 0, -1)
        frames.append(img)

    res = analyze_video_temporal_jitter(frames)
    assert res.max_landmark_drift > 0.0
    assert 0.0 <= res.jitter_anomaly_score <= 1.0
