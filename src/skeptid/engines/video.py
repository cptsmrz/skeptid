"""Video analysis engine.

Uniformly samples frames across uploaded video containers, performs multi-feature
forensic evaluation per frame, and aggregates temporal consistency and risk timelines.
"""

import os
import tempfile
from typing import Any

import cv2  # type: ignore[import-untyped]
from fastapi import HTTPException, status
from PIL import Image

from skeptid.api.validators import validate_video_bytes
from skeptid.core.config import SkeptidConfig
from skeptid.core.types import (
    IMAGE_LABELS,
    Evidence,
    Modality,
    Verdict,
)
from skeptid.forensics.ela import compute_ela
from skeptid.forensics.heatmap import generate_forensic_heatmap
from skeptid.forensics.noise import compute_noise_residual
from skeptid.forensics.spectrum import compute_spectrum

MAX_VIDEO_DURATION_S = 60.0
DEFAULT_FRAME_SAMPLES = 16


class VideoEngine:
    """Intake engine for video modality."""

    def __init__(self, config: SkeptidConfig | None = None) -> None:
        self.config = config or SkeptidConfig()
        self.samples = DEFAULT_FRAME_SAMPLES

    async def analyze(
        self,
        raw_bytes: bytes,
        filename: str | None = None,
        analysis_id: str | None = None,
    ) -> Verdict:
        """Process video bytes, extract uniform frames, and aggregate temporal risk."""
        # 1. Magic bytes validation
        fmt = validate_video_bytes(raw_bytes)

        # 2. Write to temp file for OpenCV container decoding
        suffix = f".{fmt}"
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(raw_bytes)

            cap = cv2.VideoCapture(tmp_path)
            if not cap.isOpened():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not open video file. Corrupted container or unsupported codec.",
                )

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_s = total_frames / fps if fps > 0 else 0.0

            if duration_s > MAX_VIDEO_DURATION_S:
                cap.release()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Video duration ({duration_s:.1f}s) exceeds maximum allowed limit of {MAX_VIDEO_DURATION_S}s.",
                )

            if total_frames <= 0:
                cap.release()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Video contains 0 decodable frames.",
                )

            # 3. Uniform frame index sampling
            n_samples = min(self.samples, total_frames)
            step = max(1, total_frames // n_samples)
            sample_indices = [min(i * step, total_frames - 1) for i in range(n_samples)]
            # Deduplicate while preserving order
            sample_indices = sorted(dict.fromkeys(sample_indices))

            frame_scores: list[dict[str, Any]] = []
            frame_risks: list[float] = []
            highest_risk = -1.0
            highest_risk_frame_img: Image.Image | None = None
            highest_risk_ela_img: Image.Image | None = None
            highest_risk_noise: Any | None = None

            for idx in sample_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, bgr_frame = cap.read()
                if not ret or bgr_frame is None:
                    continue

                rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb_frame)
                t_sec = round(idx / fps, 2)

                # Quick frame forensic evaluation
                ela = compute_ela(pil_img)
                spec = compute_spectrum(pil_img)
                noise = compute_noise_residual(pil_img)

                # Calculate frame risk score (0.0 to 1.0)
                frame_risk = 0.05
                if spec.peak_anomaly_score > 0.3:
                    frame_risk += 0.35
                if spec.high_freq_ratio > 0.20:
                    frame_risk += 0.25
                if noise.kurtosis_anomaly and noise.mean_variance > 20.0:
                    frame_risk += 0.30
                if ela.high_diff_block_ratio > 0.05 or ela.mean_diff > 8.0:
                    frame_risk += 0.25
                frame_risk = round(min(1.0, frame_risk), 4)

                frame_risks.append(frame_risk)
                frame_scores.append({"t": t_sec, "score": frame_risk})

                if frame_risk > highest_risk or highest_risk_frame_img is None:
                    highest_risk = frame_risk
                    highest_risk_frame_img = pil_img
                    highest_risk_ela_img = ela.diff_image
                    highest_risk_noise = noise.residual_array

            cap.release()

            if not frame_risks:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to decode any video frames for analysis.",
                )

            # 4. Temporal Aggregation
            # Formula: 0.5 * top_k_mean + 0.3 * max + 0.2 * mean
            k = min(4, len(frame_risks))
            sorted_risks = sorted(frame_risks, reverse=True)
            top_k_mean = float(sum(sorted_risks[:k]) / k)
            max_risk = float(max(frame_risks))
            mean_risk = float(sum(frame_risks) / len(frame_risks))

            video_risk = round(0.50 * top_k_mean + 0.30 * max_risk + 0.20 * mean_risk, 4)

            # 5. Temporal consistency check
            # Large jump between adjacent sampled frames raises a flag
            evidence: list[Evidence] = []
            adjacent_jumps = [
                abs(frame_risks[i] - frame_risks[i - 1])
                for i in range(1, len(frame_risks))
            ]
            max_jump = max(adjacent_jumps) if adjacent_jumps else 0.0
            if max_jump > 0.35:
                evidence.append(
                    Evidence(
                        kind="flag",
                        description=f"High frame-to-frame temporal inconsistency detected (max jump: {max_jump:.2f})",
                        payload={"max_jump": round(max_jump, 3)},
                    )
                )

            # Add frame timeline evidence
            evidence.append(
                Evidence(
                    kind="frame_score",
                    description=f"Uniform temporal frame risk timeline ({len(frame_scores)} frames)",
                    payload={"frames": frame_scores},
                )
            )

            # Add heatmap of the highest-risk frame
            if highest_risk_frame_img is not None:
                png_b64, max_anom = generate_forensic_heatmap(
                    image=highest_risk_frame_img,
                    ela_amplified_img=highest_risk_ela_img,
                    noise_residual=highest_risk_noise,
                )
                evidence.append(
                    Evidence(
                        kind="heatmap",
                        description="Forensic anomaly map of highest-risk frame",
                        payload={"png_b64": png_b64, "max_anomaly": max_anom},
                    )
                )

            # Determine level and label
            if video_risk >= 0.70:
                level = "HIGH"
                label = "ai_generated"
            elif video_risk >= 0.35:
                level = "MEDIUM"
                label = "ai_edited"
            else:
                level = "LOW"
                label = "authentic"

            label_scores = {lbl: 0.05 for lbl in IMAGE_LABELS}
            label_scores[label] = round(video_risk if label != "authentic" else (1.0 - video_risk), 4)
            # Rebalance
            tot = sum(label_scores.values())
            label_scores = {k: round(v / tot, 4) for k, v in label_scores.items()}

            provider_summary = {
                "id": "own",
                "ok": True,
                "risk": video_risk,
                "model_version": "video_forensic_v1",
                "latency_ms": 100,
                "error": None,
            }

            return Verdict(
                id=analysis_id or "vid-1",
                modality=Modality.VIDEO,
                label=label,
                risk=video_risk,
                level=level,
                confidence=round(max(0.60, 1.0 - (max_jump * 0.5)), 4),
                disagreement=False,
                primary_provider="own",
                mock=False,
                providers=[provider_summary],
                evidence=evidence,
                limits_note="Risk score with evidence, not proof.",
            )

        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
