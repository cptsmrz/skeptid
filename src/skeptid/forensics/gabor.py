"""Multi-Angle Gabor Filter Texture Regularity & Smoothing Analysis.

Analyzes directional frequency responses across multiple orientations (0°, 45°, 90°, 135°)
to detect synthetic over-smoothing, artificial skin homogenization, and GAN/diffusion texture anomalies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2  # type: ignore[import-untyped]
import numpy as np
from PIL import Image


@dataclass
class GaborTextureResult:
    """Quantitative results from multi-angle Gabor texture analysis."""

    orientation_variance: float
    mean_energy: float
    min_energy: float
    max_energy: float
    gabor_anomaly_score: float
    is_suspicious: bool
    description: str
    metadata: dict[str, Any]


def compute_gabor_texture(image: Image.Image | np.ndarray) -> GaborTextureResult:
    """Compute multi-orientation Gabor responses to quantify texture naturalness.

    Args:
        image: PIL Image or RGB/Grayscale numpy array.

    Returns:
        GaborTextureResult with directional variance and synthetic smoothing scores.
    """
    if isinstance(image, Image.Image):
        gray = np.array(image.convert("L"), dtype=np.float32)
    elif isinstance(image, np.ndarray):
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32)
        else:
            gray = image.astype(np.float32)
    else:
        raise TypeError("image must be a PIL Image or numpy array")

    h, w = gray.shape
    if h < 32 or w < 32:
        return GaborTextureResult(
            orientation_variance=0.0,
            mean_energy=0.0,
            min_energy=0.0,
            max_energy=0.0,
            gabor_anomaly_score=0.0,
            is_suspicious=False,
            description="Image too small for Gabor texture decomposition",
            metadata={},
        )

    # Scale down if very large for responsive real-time execution
    max_dim = 512
    if h > max_dim or w > max_dim:
        scale = max_dim / max(h, w)
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    # Angles to evaluate: 0, 45, 90, 135 degrees
    angles = [0.0, 45.0, 90.0, 135.0]
    energies: list[float] = []
    variances: list[float] = []

    ksize = 21
    sigma = 4.0
    lambd = 8.0
    gamma = 0.5
    psi = 0.0

    for deg in angles:
        theta = np.radians(deg)
        kernel = cv2.getGaborKernel(
            (ksize, ksize),
            sigma,
            theta,
            lambd,
            gamma,
            psi,
            ktype=cv2.CV_32F,
        )
        # DC-invariance: zero-mean normalize so flat lighting yields zero energy
        kernel -= np.mean(kernel)
        filtered = cv2.filter2D(gray, cv2.CV_32F, kernel)
        energy = float(np.mean(np.abs(filtered)))
        var = float(np.var(filtered))
        energies.append(energy)
        variances.append(var)

    orientation_var = float(np.var(energies))
    mean_energy = float(np.mean(energies))
    min_energy = float(np.min(energies))
    max_energy = float(np.max(energies))

    # Anomaly detection:
    # Synthetic diffusion portraits frequently show unnaturally low energy (< 15.0)
    # or orientation variance is near zero (< 0.5) due to synthetic bilateral/denoising smoothing.
    anomaly_score = 0.05
    reasons: list[str] = []

    if mean_energy < 12.0:
        anomaly_score += 0.35
        reasons.append("Unnaturally low Gabor texture response (severe neural over-smoothing)")
    elif mean_energy > 95.0:
        anomaly_score += 0.25
        reasons.append("Excessive Gabor energy (unnatural high-frequency texture noise)")

    if orientation_var < 0.4 and mean_energy > 5.0:
        anomaly_score += 0.30
        reasons.append("Isotropic texture uniformity (lacks organic directional variance)")

    anomaly_score = round(min(1.0, max(0.02, anomaly_score)), 4)
    is_suspicious = anomaly_score > 0.45

    description = (
        "; ".join(reasons)
        if reasons
        else f"Normal multi-angle Gabor texture energy ({mean_energy:.1f}) and directional variance ({orientation_var:.2f})"
    )

    return GaborTextureResult(
        orientation_variance=round(orientation_var, 4),
        mean_energy=round(mean_energy, 4),
        min_energy=round(min_energy, 4),
        max_energy=round(max_energy, 4),
        gabor_anomaly_score=anomaly_score,
        is_suspicious=is_suspicious,
        description=description,
        metadata={
            "angles": angles,
            "energies": [round(e, 2) for e in energies],
            "variances": [round(v, 2) for v in variances],
        },
    )
