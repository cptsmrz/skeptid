"""Error Level Analysis (ELA) for image forensics.

Re-saves images at a standardized JPEG quality and measures compression discrepancy
across 8x8 blocks to detect spliced or AI-modified regions.
"""

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageChops


@dataclass
class ELAResult:
    """Quantitative results from Error Level Analysis."""

    mean_diff: float
    max_diff: float
    block_variance: float
    high_diff_block_ratio: float
    diff_image: Image.Image


def compute_ela(
    image: Image.Image,
    quality: int = 90,
    amplification: float = 10.0,
) -> ELAResult:
    """Execute Error Level Analysis on an RGB image."""
    rgb_img = image.convert("RGB")
    buf = io.BytesIO()
    rgb_img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    resaved_img = Image.open(buf)

    # Pixel-wise difference
    diff_img = ImageChops.difference(rgb_img, resaved_img)
    diff_arr = np.array(diff_img, dtype=np.float32)

    # Amplified visual difference
    amplified_arr = np.clip(diff_arr * amplification, 0, 255).astype(np.uint8)
    amplified_img = Image.fromarray(amplified_arr)

    # Quantitative block statistics (8x8 JPEG macroblocks)
    h, w, _ = diff_arr.shape
    h_blocks = h // 8
    w_blocks = w // 8

    mean_diff = float(np.mean(diff_arr))
    max_diff = float(np.max(diff_arr))

    if h_blocks > 0 and w_blocks > 0:
        cropped = diff_arr[: h_blocks * 8, : w_blocks * 8]
        # Reshape to (h_blocks, 8, w_blocks, 8, 3) -> compute block means
        blocks = cropped.reshape(h_blocks, 8, w_blocks, 8, 3)
        block_means = blocks.mean(axis=(1, 3, 4))  # (h_blocks, w_blocks)
        block_variance = float(np.var(block_means))
        # Blocks with noticeably elevated error level compared to average
        threshold = max(3.0, mean_diff * 1.8)
        high_diff_ratio = float(np.mean(block_means > threshold))
    else:
        block_variance = float(np.var(diff_arr))
        high_diff_ratio = 0.0

    return ELAResult(
        mean_diff=round(mean_diff, 4),
        max_diff=round(max_diff, 4),
        block_variance=round(block_variance, 4),
        high_diff_block_ratio=round(high_diff_ratio, 4),
        diff_image=amplified_img,
    )
