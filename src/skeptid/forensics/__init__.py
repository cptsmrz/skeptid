"""Forensics package for text, email, and media analysis."""

from skeptid.forensics.dct import DCTAnalysisResult, compute_block_dct
from skeptid.forensics.ela import ELAResult, compute_ela
from skeptid.forensics.exif import ExifResult, analyze_exif
from skeptid.forensics.gabor import GaborTextureResult, compute_gabor_texture
from skeptid.forensics.heatmap import generate_forensic_heatmap
from skeptid.forensics.lexicon import scan_lexicon
from skeptid.forensics.noise import NoiseResult, compute_noise_residual
from skeptid.forensics.spectrum import SpectrumResult, compute_spectrum

__all__ = [
    "DCTAnalysisResult",
    "ELAResult",
    "ExifResult",
    "GaborTextureResult",
    "NoiseResult",
    "SpectrumResult",
    "analyze_exif",
    "compute_block_dct",
    "compute_ela",
    "compute_gabor_texture",
    "compute_noise_residual",
    "compute_spectrum",
    "generate_forensic_heatmap",
    "scan_lexicon",
]

