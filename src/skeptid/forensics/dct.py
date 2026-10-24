"""8x8 Block DCT (Discrete Cosine Transform) Residual Analysis.

Analyzes 8x8 JPEG compression blocks and frequency-domain AC coefficient distributions
to detect synthetic over-smoothing, diffusion noise residuals, and unnatural grid quantization.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2  # type: ignore[import-untyped]
import numpy as np
from PIL import Image


@dataclass
class DCTAnalysisResult:
    """Quantitative results from 8x8 block DCT analysis."""

    high_freq_variance: float
    high_freq_mean: float
    boundary_discontinuity_ratio: float
    dct_anomaly_score: float
    is_suspicious: bool
    description: str
    metadata: dict[str, Any]


def compute_block_dct(image: Image.Image | np.ndarray) -> DCTAnalysisResult:
    """Compute 8x8 block DCT coefficients and evaluate compression/smoothing residuals.

    Args:
        image: PIL Image or RGB/Grayscale numpy array.

    Returns:
        DCTAnalysisResult with high-frequency variance and synthetic anomaly scoring.
    """
    if isinstance(image, Image.Image):
        # Convert PIL to numpy grayscale
        gray = np.array(image.convert("L"), dtype=np.float32)
    elif isinstance(image, np.ndarray):
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32)
        else:
            gray = image.astype(np.float32)
    else:
        raise TypeError("image must be a PIL Image or numpy array")

    h, w = gray.shape
    if h < 16 or w < 16:
        return DCTAnalysisResult(
            high_freq_variance=0.0,
            high_freq_mean=0.0,
            boundary_discontinuity_ratio=1.0,
            dct_anomaly_score=0.0,
            is_suspicious=False,
            description="Image too small for 8x8 block DCT analysis",
            metadata={"blocks_analyzed": 0},
        )

    # Scale down if very large for rapid real-time analysis while keeping 8x8 grid alignment
    max_dim = 1024
    if h > max_dim or w > max_dim:
        scale = max_dim / max(h, w)
        new_w = int(w * scale // 8) * 8
        new_h = int(h * scale // 8) * 8
        gray = cv2.resize(gray, (max(8, new_w), max(8, new_h)), interpolation=cv2.INTER_AREA)
        h, w = gray.shape

    # Truncate to exact multiples of 8
    h8 = (h // 8) * 8
    w8 = (w // 8) * 8
    gray_8 = gray[:h8, :w8]

    # Pre-build high-frequency mask for 8x8 DCT matrix (frequencies where u+v >= 7)
    high_freq_mask = np.zeros((8, 8), dtype=bool)
    for u in range(8):
        for v in range(8):
            if (u + v) >= 7 and not (u == 0 and v == 0):
                high_freq_mask[u, v] = True

    # Extract 8x8 blocks and compute DCT
    high_freq_coeffs: list[np.ndarray] = []
    
    # Slice blocks with step 8
    for r in range(0, h8, 8):
        for c in range(0, w8, 8):
            block = gray_8[r : r + 8, c : c + 8]
            dct_block = cv2.dct(block)
            hf_vals = dct_block[high_freq_mask]
            high_freq_coeffs.append(hf_vals)

    hf_all = np.concatenate(high_freq_coeffs) if high_freq_coeffs else np.array([0.0])
    high_freq_variance = float(np.var(hf_all))
    high_freq_mean = float(np.mean(np.abs(hf_all)))

    # Compute block boundary discontinuity: difference across 8px boundaries vs within blocks
    # Internal horizontal diffs (skip every 8th column)
    horiz_diff = np.abs(np.diff(gray_8, axis=1))
    boundary_cols = np.arange(7, w8 - 1, 8)
    internal_cols = np.setdiff1d(np.arange(w8 - 1), boundary_cols)

    boundary_mean_diff = (
        float(np.mean(horiz_diff[:, boundary_cols])) if len(boundary_cols) > 0 else 1.0
    )
    internal_mean_diff = (
        float(np.mean(horiz_diff[:, internal_cols])) if len(internal_cols) > 0 else 1.0
    )

    ratio = boundary_mean_diff / max(internal_mean_diff, 1e-6)

    # Anomaly scoring logic:
    # 1. Unusually low high-frequency variance (< 8.0) indicates neural over-smoothing / diffusion smoothing
    # 2. Abnormally high (> 120.0) indicates high-frequency synthetic generator lattice noise
    # 3. Abnormal boundary ratio indicates missing natural JPEG block compression artifacts or grid warping
    anomaly_score = 0.05
    reasons: list[str] = []

    if high_freq_variance < 8.0:
        anomaly_score += 0.35
        reasons.append("Unnaturally low 8x8 DCT high-frequency coefficient variance (neural smoothing)")
    elif high_freq_variance > 140.0:
        anomaly_score += 0.30
        reasons.append("Elevated high-frequency DCT noise residual typical of generative lattices")

    if high_freq_mean < 1.5:
        anomaly_score += 0.25
        reasons.append("Depleted high-frequency energy in DCT subbands")

    if ratio > 2.5:
        anomaly_score += 0.25
        reasons.append(f"Severe block boundary discontinuity ratio ({ratio:.2f})")

    anomaly_score = round(min(1.0, max(0.02, anomaly_score)), 4)
    is_suspicious = anomaly_score > 0.45

    description = (
        "; ".join(reasons)
        if reasons
        else f"Normal 8x8 DCT high-frequency variance ({high_freq_variance:.2f}) and boundary ratio ({ratio:.2f})"
    )

    return DCTAnalysisResult(
        high_freq_variance=round(high_freq_variance, 4),
        high_freq_mean=round(high_freq_mean, 4),
        boundary_discontinuity_ratio=round(ratio, 4),
        dct_anomaly_score=anomaly_score,
        is_suspicious=is_suspicious,
        description=description,
        metadata={
            "blocks_analyzed": len(high_freq_coeffs),
            "sampled_shape": [h8, w8],
        },
    )
