"""2D FFT spectrum analysis for image forensics.

Computes the 2D Fourier Transform and radially averaged power spectrum to detect
periodic upsampling artifacts and spectral decay anomalies characteristic of AI generation.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class SpectrumResult:
    """Quantitative results from 2D FFT spectral analysis."""

    high_freq_ratio: float
    radial_decay_slope: float
    peak_anomaly_score: float
    azimuthal_variance: float


def compute_spectrum(image: Image.Image) -> SpectrumResult:
    """Analyze the 2D Fourier power spectrum of an image."""
    gray = image.convert("L")
    arr = np.array(gray, dtype=np.float32)
    h, w = arr.shape

    # Normalize image to zero mean
    norm_arr = arr - np.mean(arr)

    # 2D FFT and power spectrum
    f_transform = np.fft.fft2(norm_arr)
    f_shift = np.fft.fftshift(f_transform)
    power_spectrum = np.abs(f_shift) ** 2

    # Radial coordinates from center
    cy, cx = h // 2, w // 2
    y_indices, x_indices = np.indices((h, w))
    radii = np.sqrt((x_indices - cx) ** 2 + (y_indices - cy) ** 2).astype(np.int32)
    max_radius = min(cy, cx)

    if max_radius < 4:
        return SpectrumResult(
            high_freq_ratio=0.0,
            radial_decay_slope=0.0,
            peak_anomaly_score=0.0,
            azimuthal_variance=0.0,
        )

    # Radially averaged power spectrum
    radial_profile = np.zeros(max_radius, dtype=np.float32)
    for r in range(max_radius):
        mask = radii == r
        if np.any(mask):
            radial_profile[r] = float(np.mean(power_spectrum[mask]))

    total_power = float(np.sum(radial_profile)) + 1e-12
    # High frequency energy in upper third of radial spectrum
    high_freq_start = int(max_radius * 0.70)
    high_freq_power = float(np.sum(radial_profile[high_freq_start:]))
    high_freq_ratio = high_freq_power / total_power

    # Fit decay slope in log-log space (natural images follow 1/f^alpha ~ -2.0)
    r_valid = np.arange(1, max_radius)
    p_valid = radial_profile[1:] + 1e-12
    log_r = np.log(r_valid)
    log_p = np.log(p_valid)
    slope, _ = np.polyfit(log_r, log_p, 1)

    # Detect high-frequency periodic lattice spikes
    # Standard natural image spectra decrease monotonically; sharp spikes indicate GAN/diffusion grid artifacts
    log_power = np.log1p(power_spectrum)
    norm_log_power = (log_power - np.mean(log_power)) / (np.std(log_power) + 1e-12)
    # Spikes outside the DC center (> 3 std dev)
    dc_mask = radii > 10
    spikes = np.sum((norm_log_power > 3.2) & dc_mask)
    peak_anomaly_score = float(min(1.0, spikes / 100.0))

    # Azimuthal variance (directional asymmetry)
    azimuthal_variance = float(np.var(radial_profile / (np.mean(radial_profile) + 1e-12)))

    return SpectrumResult(
        high_freq_ratio=round(high_freq_ratio, 4),
        radial_decay_slope=round(float(slope), 4),
        peak_anomaly_score=round(peak_anomaly_score, 4),
        azimuthal_variance=round(min(100.0, azimuthal_variance), 4),
    )
