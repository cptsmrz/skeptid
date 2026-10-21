"""Unit tests for payload validators and magic byte detection."""

import pytest
from fastapi import HTTPException

from skeptid.api.validators import (
    JPEG_MAGIC,
    MAX_IMAGE_BYTES,
    PNG_MAGIC,
    normalize_text,
    validate_image_bytes,
    validate_text,
)


def test_normalize_text() -> None:
    # Full-width characters normalized to ASCII via NFKC
    raw = "Ｈｅｌｌｏ Ｗｏｒｌｄ   "
    assert normalize_text(raw) == "Hello World"


def test_validate_text_limits() -> None:
    # Empty string raises 400
    with pytest.raises(HTTPException) as exc_info:
        validate_text("   ")
    assert exc_info.value.status_code == 400

    # Over 20,000 characters raises 400
    long_text = "a" * 20001
    with pytest.raises(HTTPException) as exc_info:
        validate_text(long_text)
    assert exc_info.value.status_code == 400

    # Valid text
    valid = "Please verify your account credentials immediately."
    assert validate_text(valid) == valid


def test_validate_image_magic_bytes() -> None:
    # JPEG magic bytes
    jpeg_data = JPEG_MAGIC + b"\x00" * 20
    assert validate_image_bytes(jpeg_data) == "jpeg"

    # PNG magic bytes
    png_data = PNG_MAGIC + b"\x00" * 20
    assert validate_image_bytes(png_data) == "png"

    # WebP magic bytes: RIFF????WEBP
    webp_data = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 10
    assert validate_image_bytes(webp_data) == "webp"

    # Unsupported format
    with pytest.raises(HTTPException) as exc_info:
        validate_image_bytes(b"GIF89a" + b"\x00" * 20)
    assert exc_info.value.status_code == 400

    # File size limit
    oversized = JPEG_MAGIC + b"\x00" * (MAX_IMAGE_BYTES + 1)
    with pytest.raises(HTTPException) as exc_info:
        validate_image_bytes(oversized)
    assert exc_info.value.status_code == 413
