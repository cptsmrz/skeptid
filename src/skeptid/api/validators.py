"""Input validation, unicode normalization, and magic-byte checks."""

import unicodedata

from fastapi import HTTPException, status

MAX_TEXT_CHARS = 20000
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MB

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_RIFF = b"RIFF"
WEBP_MARKER = b"WEBP"


def normalize_text(text: str) -> str:
    """Normalize input text with Unicode NFKC and strip excessive trailing whitespace."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    return normalized.strip()


def validate_text(text: str) -> str:
    """Validate and normalize text input payload."""
    if not text or not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty.",
        )
    normalized = normalize_text(text)
    if len(normalized) > MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Text length exceeds maximum allowed limit of {MAX_TEXT_CHARS} characters.",
        )
    return normalized


def validate_image_bytes(data: bytes) -> str:
    """Validate image magic bytes and size limit. Returns detected format."""
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Image exceeds maximum size of {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
        )
    if len(data) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image payload: file too small.",
        )

    if data.startswith(JPEG_MAGIC):
        return "jpeg"
    if data.startswith(PNG_MAGIC):
        return "png"
    if data.startswith(WEBP_RIFF) and data[8:12] == WEBP_MARKER:
        return "webp"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported image format. Allowed formats: JPEG, PNG, WebP (magic-byte validated).",
    )


def validate_video_bytes(data: bytes) -> str:
    """Validate video magic bytes and size limit. Returns detected format."""
    if len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Video exceeds maximum size of {MAX_VIDEO_BYTES // (1024 * 1024)} MB.",
        )
    if len(data) < 16:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid video payload: file too small.",
        )

    # MP4 / QuickTime: bytes 4..8 == 'ftyp'
    if data[4:8] == b"ftyp":
        return "mp4"
    # WebM / Matroska: \x1a\x45\xdf\xa3
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    # AVI: RIFF....AVI
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return "avi"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported video format. Allowed formats: MP4, WebM, AVI (magic-byte validated).",
    )


def detect_media_type(data: bytes) -> tuple[str, str]:
    """Inspect magic bytes to determine if media is 'image' or 'video' and format.

    Returns:
        (media_type, format_name) where media_type is 'image' or 'video'.
    """
    if len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="File exceeds maximum allowable media upload size.",
        )
    if len(data) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid media payload: file too small.",
        )

    # Check images first
    if data.startswith(JPEG_MAGIC):
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Image exceeds maximum size of {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
            )
        return "image", "jpeg"
    if data.startswith(PNG_MAGIC):
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Image exceeds maximum size of {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
            )
        return "image", "png"
    if data.startswith(WEBP_RIFF) and data[8:12] == WEBP_MARKER:
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Image exceeds maximum size of {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
            )
        return "image", "webp"

    # Check video
    if data[4:8] == b"ftyp":
        return "video", "mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "video", "webm"
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return "video", "avi"

    # Check audio
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio", "wav"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio", "mp3"
    if data[:4] == b"OggS":
        return "audio", "ogg"
    if data[:4] == b"fLaC":
        return "audio", "flac"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported media format. Magic bytes must match JPEG, PNG, WebP (image) or MP4, WebM, AVI (video).",
    )
