"""Image analysis engine.

Validates image payloads (decompression bomb protection, dimensions, magic bytes)
and delegates concurrent provider execution to the Orchestrator.
"""

import io

from fastapi import HTTPException, status
from PIL import Image

from skeptid.api.validators import validate_image_bytes
from skeptid.core.orchestrator import Orchestrator
from skeptid.core.types import AnalysisInput, Modality, Verdict

# Guard against decompression bomb vulnerabilities (spec 6.3: max 8192 px side)
MAX_SIDE_PX = 8192
Image.MAX_IMAGE_PIXELS = MAX_SIDE_PX * MAX_SIDE_PX


class ImageEngine:
    """Intake engine for image modality."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator

    async def analyze(
        self,
        raw_bytes: bytes,
        filename: str | None = None,
        analysis_id: str | None = None,
    ) -> Verdict:
        """Validate image dimensions and execute orchestrated multi-provider analysis."""
        # 1. Magic-byte and size validation
        validate_image_bytes(raw_bytes)

        # 2. Decompression bomb and dimension validation
        try:
            with Image.open(io.BytesIO(raw_bytes)) as img:
                w, h = img.size
                if w > MAX_SIDE_PX or h > MAX_SIDE_PX:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Image dimensions ({w}x{h}) exceed maximum allowable side length of {MAX_SIDE_PX} px.",
                    )
        except HTTPException:
            raise
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Corrupted or invalid image file: {exc}",
            ) from exc

        # 3. Dispatch through orchestrator
        payload = AnalysisInput(
            modality=Modality.IMAGE,
            raw_bytes=raw_bytes,
            filename=filename,
            metadata={"width": w, "height": h},
        )
        return await self.orchestrator.analyze(payload, analysis_id=analysis_id)
