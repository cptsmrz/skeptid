"""Video Temporal Landmark & Motion Jitter Forensics.

Tracks facial and salient feature landmarks across consecutive video frames using sparse
Lucas-Kanade optical flow, evaluating trajectory divergence, landmark jitter, and frame-to-frame
motion inconsistencies typical of face-swaps, deepfake flicker, and generative video warping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2  # type: ignore[import-untyped]
import numpy as np
from PIL import Image


@dataclass
class VideoTemporalJitterResult:
    """Quantitative results from video landmark and temporal motion jitter analysis."""

    mean_motion_jitter: float
    max_landmark_drift: float
    direction_entropy: float
    jitter_anomaly_score: float
    is_suspicious: bool
    description: str
    metadata: dict[str, Any]


def analyze_video_temporal_jitter(
    frames: list[np.ndarray | Image.Image],
) -> VideoTemporalJitterResult:
    """Track landmarks and evaluate motion direction consistency across video frames.

    Args:
        frames: Ordered sequence of sampled video frames (RGB/BGR numpy arrays or PIL Images).

    Returns:
        VideoTemporalJitterResult containing motion drift, direction entropy, and anomaly score.
    """
    if len(frames) < 2:
        return VideoTemporalJitterResult(
            mean_motion_jitter=0.0,
            max_landmark_drift=0.0,
            direction_entropy=0.0,
            jitter_anomaly_score=0.0,
            is_suspicious=False,
            description="Insufficient frames for temporal landmark jitter analysis (need >= 2)",
            metadata={"frames_analyzed": len(frames)},
        )

    # Convert all frames to grayscale numpy arrays
    gray_frames: list[np.ndarray] = []
    for f in frames:
        if isinstance(f, Image.Image):
            gray = np.array(f.convert("L"), dtype=np.uint8)
        elif isinstance(f, np.ndarray):
            if f.ndim == 3:
                gray = cv2.cvtColor(f, cv2.COLOR_RGB2GRAY if f.shape[2] == 3 else cv2.COLOR_BGR2GRAY)
            else:
                gray = f.astype(np.uint8)
        else:
            continue
        
        # Scale to standard height of 360 for consistent cross-resolution tracking
        if gray.shape[0] != 360:
            scale = 360.0 / max(gray.shape[0], 1)
            new_w = max(16, int(gray.shape[1] * scale))
            gray = cv2.resize(gray, (new_w, 360), interpolation=cv2.INTER_AREA)

        gray_frames.append(gray)

    if len(gray_frames) < 2:
        return VideoTemporalJitterResult(
            mean_motion_jitter=0.0,
            max_landmark_drift=0.0,
            direction_entropy=0.0,
            jitter_anomaly_score=0.0,
            is_suspicious=False,
            description="Failed to convert frames for video motion analysis",
            metadata={"frames_analyzed": len(gray_frames)},
        )

    pair_jitters: list[float] = []
    pair_drifts: list[float] = []
    direction_variances: list[float] = []
    total_tracked_points = 0

    lk_params = dict(
        winSize=(19, 19),
        maxLevel=2,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
    )

    for i in range(len(gray_frames) - 1):
        prev_gray = gray_frames[i]
        curr_gray = gray_frames[i + 1]

        # Detect salient corners / facial landmarks
        # Higher density in central 70% of frame where faces/subjects reside
        h, w = prev_gray.shape
        mask = np.zeros_like(prev_gray)
        y0, y1 = int(h * 0.15), int(h * 0.85)
        x0, x1 = int(w * 0.15), int(w * 0.85)
        mask[y0:y1, x0:x1] = 255

        pts0 = cv2.goodFeaturesToTrack(
            prev_gray,
            maxCorners=64,
            qualityLevel=0.015,
            minDistance=8,
            mask=mask,
        )

        if pts0 is None or len(pts0) < 4:
            # Fallback across the full frame if central subject was featureless
            pts0 = cv2.goodFeaturesToTrack(
                prev_gray,
                maxCorners=64,
                qualityLevel=0.015,
                minDistance=8,
            )

        if pts0 is None or len(pts0) < 4:
            continue

        pts1, status, _ = cv2.calcOpticalFlowPyrLK(prev_gray, curr_gray, pts0, None, **lk_params)
        if pts1 is None or status is None:
            continue

        good_mask = (status.flatten() == 1)
        good_pts0 = pts0[good_mask].reshape(-1, 2)
        good_pts1 = pts1[good_mask].reshape(-1, 2)

        if len(good_pts0) < 4:
            continue

        total_tracked_points += len(good_pts0)

        # Displacement vectors
        displacements = good_pts1 - good_pts0
        dx = displacements[:, 0]
        dy = displacements[:, 1]
        magnitudes = np.sqrt(dx**2 + dy**2)

        # Direction angles (-pi to +pi)
        angles = np.arctan2(dy, dx)

        # Measure motion direction consistency
        # In natural camera / head movement, points move in consistent directions
        # In face-swapped / warped videos, local features jitter with high angle variance
        angle_var = float(np.var(angles))
        direction_variances.append(angle_var)

        # Measure landmark drift magnitude
        mean_drift = float(np.mean(magnitudes))
        pair_drifts.append(mean_drift)

        # Acceleration / jitter: deviation from mean frame motion
        mean_vec = np.mean(displacements, axis=0)
        vec_jitter = np.sqrt(np.sum((displacements - mean_vec) ** 2, axis=1))
        pair_jitters.append(float(np.mean(vec_jitter)))

    if not pair_jitters:
        return VideoTemporalJitterResult(
            mean_motion_jitter=0.0,
            max_landmark_drift=0.0,
            direction_entropy=0.0,
            jitter_anomaly_score=0.05,
            is_suspicious=False,
            description="Static sequence or minimal trackable feature motion",
            metadata={"frames_analyzed": len(gray_frames), "tracked_points": 0},
        )

    mean_motion_jitter = float(np.mean(pair_jitters))
    max_landmark_drift = float(np.max(pair_drifts)) if pair_drifts else 0.0
    mean_direction_var = float(np.mean(direction_variances)) if direction_variances else 0.0

    # Temporal jump spikes between consecutive frames
    jitter_jumps = [
        abs(pair_jitters[j] - pair_jitters[j - 1]) for j in range(1, len(pair_jitters))
    ]
    max_jitter_jump = float(np.max(jitter_jumps)) if jitter_jumps else 0.0

    # Score calculation
    # High local landmark jitter (> 3.5 px), high direction variance (> 2.0),
    # or sudden spikes (> 4.0 px) indicate facial warping or face-swap flicker
    anomaly_score = 0.05
    reasons: list[str] = []

    if mean_motion_jitter > 3.8:
        anomaly_score += 0.35
        reasons.append(f"Elevated landmark trajectory jitter ({mean_motion_jitter:.2f} px)")
    elif mean_motion_jitter > 2.2:
        anomaly_score += 0.20
        reasons.append(f"Moderate landmark micro-jitter ({mean_motion_jitter:.2f} px)")

    if max_jitter_jump > 3.5:
        anomaly_score += 0.30
        reasons.append(f"Abrupt temporal landmark jump between frames ({max_jitter_jump:.2f} px)")

    if mean_direction_var > 2.2:
        anomaly_score += 0.25
        reasons.append("Chaotic multi-directional feature drift (facial boundary instability)")

    anomaly_score = round(min(1.0, max(0.02, anomaly_score)), 4)
    is_suspicious = anomaly_score > 0.45

    description = (
        "; ".join(reasons)
        if reasons
        else f"Smooth landmark trajectory (jitter: {mean_motion_jitter:.2f} px, max jump: {max_jitter_jump:.2f} px)"
    )

    return VideoTemporalJitterResult(
        mean_motion_jitter=round(mean_motion_jitter, 4),
        max_landmark_drift=round(max_landmark_drift, 4),
        direction_entropy=round(mean_direction_var, 4),
        jitter_anomaly_score=anomaly_score,
        is_suspicious=is_suspicious,
        description=description,
        metadata={
            "frames_analyzed": len(gray_frames),
            "tracked_points_sum": total_tracked_points,
            "max_jitter_jump": round(max_jitter_jump, 3),
        },
    )
