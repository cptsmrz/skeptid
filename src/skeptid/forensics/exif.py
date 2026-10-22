"""Metadata, EXIF, and quantization table forensic analysis.

Evaluates metadata provenance, camera tags, generator/editor signatures,
and JPEG quantization tables.
"""

from dataclasses import dataclass, field
from typing import Any

from PIL import ExifTags, Image

AI_SOFTWARE_KEYWORDS = [
    "midjourney",
    "stable diffusion",
    "dall-e",
    "novelai",
    "comfyui",
    "automatic1111",
    "invokeai",
    "firefly",
    "bing image creator",
]

EDITING_SOFTWARE_KEYWORDS = [
    "photoshop",
    "gimp",
    "lightroom",
    "snapseed",
    "affinity",
    "vsco",
]


@dataclass
class ExifResult:
    """Forensic metadata and quantization evaluation."""

    has_exif: bool
    software_tag: str | None
    is_ai_software: bool
    is_editing_software: bool
    has_camera_info: bool
    camera_make: str | None
    camera_model: str | None
    has_quantization_tables: bool
    dimension_anomaly: bool
    raw_tags: dict[str, Any] = field(default_factory=dict)


def analyze_exif(image: Image.Image) -> ExifResult:
    """Analyze EXIF tags, software signatures, and quantization tables."""
    raw_tags: dict[str, Any] = {}
    software_tag: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None

    try:
        exif = image.getexif()
        if exif:
            for tag_id, val in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                raw_tags[tag_name] = str(val)[:128]

            software_tag = raw_tags.get("Software")
            camera_make = raw_tags.get("Make")
            camera_model = raw_tags.get("Model")
    except (AttributeError, ValueError, OSError):
        pass

    has_exif = len(raw_tags) > 0
    has_camera_info = bool(camera_make or camera_model)

    # Check software signatures
    soft_lower = (software_tag or "").lower()
    is_ai_software = any(k in soft_lower for k in AI_SOFTWARE_KEYWORDS)
    is_editing_software = any(k in soft_lower for k in EDITING_SOFTWARE_KEYWORDS)

    # Check JPEG quantization tables
    has_quant_tables = hasattr(image, "quantization") and bool(image.quantization)

    # Dimension anomaly: exact square 512, 768, 1024 without camera metadata
    w, h = image.size
    is_generator_dim = (w, h) in [(512, 512), (768, 768), (1024, 1024), (2048, 2048), (1024, 768), (768, 1024)]
    dimension_anomaly = is_generator_dim and not has_camera_info

    return ExifResult(
        has_exif=has_exif,
        software_tag=software_tag,
        is_ai_software=is_ai_software,
        is_editing_software=is_editing_software,
        has_camera_info=has_camera_info,
        camera_make=camera_make,
        camera_model=camera_model,
        has_quantization_tables=has_quant_tables,
        dimension_anomaly=dimension_anomaly,
        raw_tags=raw_tags,
    )
