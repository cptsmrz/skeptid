"""Unit tests for 8x8 block DCT and multi-angle Gabor texture forensics."""

import numpy as np
import pytest
from PIL import Image

from skeptid.forensics.dct import DCTAnalysisResult, compute_block_dct
from skeptid.forensics.gabor import GaborTextureResult, compute_gabor_texture


def test_dct_analysis_flat_and_noisy_image() -> None:
    # 1. Uniform flat image (over-smoothed)
    flat_arr = np.full((128, 128), 120, dtype=np.uint8)
    flat_img = Image.fromarray(flat_arr)
    res_flat = compute_block_dct(flat_img)

    assert isinstance(res_flat, DCTAnalysisResult)
    assert res_flat.high_freq_variance == 0.0
    assert res_flat.dct_anomaly_score >= 0.35  # Flags unnatural lack of HF variance

    # 2. Noisy / textured image
    rng = np.random.RandomState(42)
    noise_arr = rng.randint(50, 200, (128, 128), dtype=np.uint8)
    noise_img = Image.fromarray(noise_arr)
    res_noise = compute_block_dct(noise_img)

    assert res_noise.high_freq_variance > 10.0
    assert res_noise.high_freq_mean > 0.0
    assert "blocks_analyzed" in res_noise.metadata
    assert res_noise.metadata["blocks_analyzed"] == 256  # (128/8) * (128/8) = 16*16 = 256


def test_dct_small_image_edge_case() -> None:
    small_arr = np.zeros((8, 8), dtype=np.uint8)
    res = compute_block_dct(small_arr)
    assert res.dct_anomaly_score == 0.0
    assert not res.is_suspicious


def test_gabor_texture_analysis() -> None:
    # 1. Isotropic uniform image
    uniform_arr = np.full((128, 128), 128, dtype=np.uint8)
    res_uniform = compute_gabor_texture(uniform_arr)

    assert isinstance(res_uniform, GaborTextureResult)
    assert res_uniform.orientation_variance <= 0.01
    assert res_uniform.mean_energy <= 0.01

    # 2. Anisotropic directional stripes (e.g. horizontal grating)
    stripes = np.zeros((128, 128), dtype=np.uint8)
    stripes[::4, :] = 255
    res_stripes = compute_gabor_texture(stripes)

    assert res_stripes.mean_energy > 0.0
    # Different angles should yield distinct responses
    assert len(res_stripes.metadata["energies"]) == 4
