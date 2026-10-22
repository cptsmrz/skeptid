"""High-pass filter noise residual analysis for image forensics.

Extracts sensor noise residuals and evaluates statistical moments (variance, skewness, kurtosis)
and cross-channel correlations to detect synthetic generation artifacts.
"""

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter
from scipy import stats  # type: ignore[import-untyped]


@dataclass
class NoiseResult:
    """Quantitative results from high-pass noise residual extraction."""

    mean_variance: float
    mean_kurtosis: float
    channel_variance_ratio: float
    kurtosis_anomaly: bool
    residual_array: np.ndarray


def compute_noise_residual(image: Image.Image) -> NoiseResult:
    """Extract and analyze high-pass noise residuals from an RGB image."""
    rgb_img = image.convert("RGB")
    orig_arr = np.array(rgb_img, dtype=np.float32)

    # Low-pass filtered image via 3x3 median blur
    filtered_img = rgb_img.filter(ImageFilter.MedianFilter(size=3))
    filt_arr = np.array(filtered_img, dtype=np.float32)

    # High-pass residual: I - Median(I)
    residual = orig_arr - filt_arr

    variances: list[float] = []
    kurtoses: list[float] = []

    for c in range(3):
        ch = residual[:, :, c].flatten()
        var = float(np.var(ch))
        variances.append(var)
        kurt = float(stats.kurtosis(ch))
        kurtoses.append(kurt)

    mean_var = float(np.mean(variances))
    mean_kurt = float(np.mean(kurtoses))

    # Variance balance across channels
    min_v = max(1e-4, min(variances))
    max_v = max(variances)
    var_ratio = float(max_v / min_v)

    # In natural images, noise residual is Laplacian-like with moderate kurtosis.
    # Highly flattened or unnaturally spiked kurtosis indicates synthetic diffusion/upsampling.
    kurtosis_anomaly = mean_kurt > 8.0 or mean_kurt < 0.5 or mean_var < 0.2

    return NoiseResult(
        mean_variance=round(mean_var, 4),
        mean_kurtosis=round(mean_kurt, 4),
        channel_variance_ratio=round(var_ratio, 4),
        kurtosis_anomaly=kurtosis_anomaly,
        residual_array=residual,
    )
