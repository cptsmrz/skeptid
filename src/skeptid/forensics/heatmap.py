"""Forensic anomaly map (heatmap) generator.

Combines block-level Error Level Analysis (ELA) and noise residual variance
into a colorized RGBA anomaly overlay encoded as base64 PNG.
"""

import base64
import io

import numpy as np
from PIL import Image


def generate_forensic_heatmap(
    image: Image.Image,
    ela_amplified_img: Image.Image | None = None,
    noise_residual: np.ndarray | None = None,
) -> tuple[str, float]:
    """Generate a colorized forensic anomaly heatmap overlay as a base64 PNG string.

    Returns:
        (png_b64, max_anomaly_score)
    """
    w, h = image.size

    # 1. ELA component
    if ela_amplified_img is not None:
        ela_arr = np.array(ela_amplified_img.convert("L"), dtype=np.float32)
    else:
        ela_arr = np.zeros((h, w), dtype=np.float32)

    # 2. Noise residual component
    if noise_residual is not None:
        noise_mag = np.mean(np.abs(noise_residual), axis=2)
    else:
        noise_mag = np.zeros((h, w), dtype=np.float32)

    # Normalize each channel into 0.0 - 1.0 range
    p95_ela = float(np.percentile(ela_arr, 95)) + 1e-6
    norm_ela = np.clip(ela_arr / p95_ela, 0.0, 1.0)

    p95_noise = float(np.percentile(noise_mag, 95)) + 1e-6
    norm_noise = np.clip(noise_mag / p95_noise, 0.0, 1.0)

    # Composite anomaly intensity map (0.0 to 1.0)
    anomaly_map = (0.60 * norm_ela + 0.40 * norm_noise).astype(np.float32)
    max_anomaly = float(np.max(anomaly_map))

    # Downsample / smooth into 16x16 block grid to eliminate high-frequency noise
    block_h = max(1, h // 16)
    block_w = max(1, w // 16)
    small_map = Image.fromarray((anomaly_map * 255).astype(np.uint8)).resize(
        (block_w, block_h), resample=Image.Resampling.BILINEAR
    )
    smooth_map = small_map.resize((w, h), resample=Image.Resampling.BILINEAR)
    smooth_arr = np.array(smooth_map, dtype=np.float32) / 255.0

    # Colorize: Turbo / Jet colormap approximation (Blue -> Cyan -> Yellow -> Red)
    # Alpha channel: transparent in low anomaly regions (0.0 - 0.2), increasing to 0.75 in anomalies
    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    # Blue: low, Green: mid, Red: high
    val = smooth_arr
    r_ch = np.clip((val - 0.35) * 3.0 * 255, 0, 255).astype(np.uint8)
    g_ch = np.clip(np.sin(val * np.pi) * 220, 0, 255).astype(np.uint8)
    b_ch = np.clip((0.65 - val) * 2.5 * 255, 0, 255).astype(np.uint8)
    alpha_ch = np.clip((val - 0.15) * 1.5 * 180, 0, 190).astype(np.uint8)

    rgba[:, :, 0] = r_ch
    rgba[:, :, 1] = g_ch
    rgba[:, :, 2] = b_ch
    rgba[:, :, 3] = alpha_ch

    overlay_img = Image.fromarray(rgba, mode="RGBA")
    buf = io.BytesIO()
    overlay_img.save(buf, format="PNG")
    png_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return png_b64, round(max_anomaly, 4)
