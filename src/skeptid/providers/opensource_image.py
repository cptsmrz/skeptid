"""P2 Open-source image classification provider adapting Hugging Face ViT model.

Uses 'dima806/ai_vs_human_generated_image_detection' (Apache-2.0 licence).
Features lazy loading, clean fallback, and calibration over standard IMAGE_LABELS.
"""

import io
import logging
import time
from pathlib import Path
from typing import Any

from PIL import Image

from skeptid.core.interfaces import Provider
from skeptid.core.types import (
    IMAGE_LABELS,
    AnalysisInput,
    Evidence,
    Modality,
    ProviderResult,
)

logger = logging.getLogger(__name__)

DEFAULT_IMAGE_MODEL = "dima806/ai_vs_human_generated_image_detection"


class OpenSourceImageProvider(Provider):
    """P2 image classifier adapting a Hugging Face ViT image-classification checkpoint."""

    def __init__(
        self,
        provider_id: str = "opensource_image",
        model_name: str = DEFAULT_IMAGE_MODEL,
    ) -> None:
        self.id = provider_id
        self.modality = Modality.IMAGE
        self.model_name = model_name
        self._classifier: Any | None = None
        self._initialized = False

    def _ensure_model(self) -> bool:
        """Attempt lazy loading of Hugging Face image classification pipeline."""
        if self._initialized:
            return self._classifier is not None

        self._initialized = True
        try:
            from transformers import pipeline  # type: ignore[import-untyped]

            self._classifier = pipeline(
                "image-classification",
                model=self.model_name,
                top_k=None,
            )
            logger.info("Successfully loaded open-source image model: %s", self.model_name)
        except (ImportError, ModuleNotFoundError, RuntimeError, ValueError, OSError) as exc:
            logger.warning("Failed to load open-source image model '%s': %s", self.model_name, exc)
            self._classifier = None

        return self._classifier is not None

    async def health(self) -> bool:
        """Health check returns True if the classification model is operational."""
        return self._ensure_model()

    async def analyze(self, payload: AnalysisInput) -> ProviderResult:
        """Execute image classification using fine-tuned ViT."""
        t0 = time.perf_counter()

        # 1. Parse Image from bytes or file path
        image: Image.Image | None = None
        if payload.raw_bytes:
            try:
                image = Image.open(io.BytesIO(payload.raw_bytes)).convert("RGB")
            except (OSError, ValueError):
                image = None
        elif payload.filename and Path(payload.filename).exists():
            try:
                image = Image.open(payload.filename).convert("RGB")
            except (OSError, ValueError):
                image = None

        if image is None:
            return ProviderResult(
                provider_id=self.id,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=int((time.perf_counter() - t0) * 1000),
                model_version=f"vit:{self.model_name}",
                coverage=list(IMAGE_LABELS),
                error="invalid_or_missing_image_payload",
                validated=False,
            )

        # 2. Check model availability with clean fallback
        if not self._ensure_model():
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return ProviderResult(
                provider_id=self.id,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=latency_ms,
                model_version="vit_ai_detector_stub",
                coverage=[],
                error="optional_dependency_not_installed",
                validated=False,
            )

        # 3. Model Inference
        try:
            raw_output = self._classifier(image)
            # raw_output is list of dicts: [{'label': 'AI-generated', 'score': 0.98}, {'label': 'human', 'score': 0.02}]
            scores_by_label: dict[str, float] = {}
            for item in raw_output:
                lbl = str(item.get("label", "")).strip().lower()
                scores_by_label[lbl] = float(item.get("score", 0.0))

            p_ai = scores_by_label.get("ai-generated", scores_by_label.get("1", 0.0))
            p_human = scores_by_label.get("human", scores_by_label.get("0", 0.0))

            # Normalize probabilities if sum deviates from 1.0
            total_prob = p_ai + p_human
            if total_prob > 0:
                p_ai = p_ai / total_prob
                p_human = p_human / total_prob

            # Calibrate over the 4 standard IMAGE_LABELS
            # "authentic", "filtered", "ai_edited", "ai_generated"
            calibrated = {
                "authentic": round(p_human * 0.90, 4),
                "filtered": round(p_human * 0.10, 4),
                "ai_edited": round(p_ai * 0.25, 4),
                "ai_generated": round(p_ai * 0.75, 4),
            }
            # Rebalance to sum to 1.0
            sum_cal = sum(calibrated.values())
            if sum_cal > 0:
                calibrated = {lbl: round(val / sum_cal, 4) for lbl, val in calibrated.items()}

            risk = round(p_ai, 4)
            latency_ms = max(1, int((time.perf_counter() - t0) * 1000))

            evidence = [
                Evidence(
                    kind="metric",
                    description=(
                        f"ViT OpenSource AI Image Detector ({self.model_name}): "
                        f"{p_ai:.1%} AI-generated probability (human: {p_human:.1%})"
                    ),
                    payload={
                        "model": self.model_name,
                        "p_ai": round(p_ai, 4),
                        "p_human": round(p_human, 4),
                        "license": "Apache-2.0",
                    },
                )
            ]

            return ProviderResult(
                provider_id=self.id,
                ok=True,
                label_scores=calibrated,
                risk=risk,
                evidence=evidence,
                latency_ms=latency_ms,
                model_version=f"vit:{self.model_name}",
                coverage=list(IMAGE_LABELS),
                validated=False,
            )

        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            logger.warning("Error running ViT inference on image: %s", exc)
            return ProviderResult(
                provider_id=self.id,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=int((time.perf_counter() - t0) * 1000),
                model_version=f"vit:{self.model_name}",
                coverage=[],
                error=str(exc),
                validated=False,
            )
