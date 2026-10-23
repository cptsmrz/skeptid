"""P3 Own image provider executing multi-feature forensic analysis.

Combines Error Level Analysis (ELA), 2D Fourier power spectrum, noise residual moments,
and EXIF/metadata inspection to classify images across 4 IMAGE_LABELS.
"""

import io
import time
from pathlib import Path

from PIL import Image

from skeptid.core.interfaces import Provider
from skeptid.core.types import (
    IMAGE_LABELS,
    AnalysisInput,
    Evidence,
    Modality,
    ProviderResult,
)
from skeptid.forensics.ela import compute_ela
from skeptid.forensics.exif import analyze_exif
from skeptid.forensics.heatmap import generate_forensic_heatmap
from skeptid.forensics.noise import compute_noise_residual
from skeptid.forensics.spectrum import compute_spectrum


class OwnImageProvider(Provider):
    """P3 forensic image classifier with anomaly heatmap generation."""

    def __init__(self, provider_id: str = "own") -> None:
        self.id = provider_id
        self.modality = Modality.IMAGE

    async def health(self) -> bool:
        """Health check returns True since standard forensic extractors are self-contained."""
        return True

    async def analyze(self, payload: AnalysisInput) -> ProviderResult:
        """Execute forensic extraction, score IMAGE_LABELS, and generate heatmap."""
        t0 = time.perf_counter()

        # Load image from raw bytes or filename
        image: Image.Image | None = None
        if payload.raw_bytes:
            try:
                image = Image.open(io.BytesIO(payload.raw_bytes))
            except (OSError, ValueError):
                image = None
        elif payload.filename and Path(payload.filename).exists():
            try:
                image = Image.open(payload.filename)
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
                model_version="heuristic_v0",
                coverage=list(IMAGE_LABELS),
                error="invalid_or_missing_image_payload",
                validated=False,
            )

        # 1. Execute forensic extractors
        ela_res = compute_ela(image)
        spec_res = compute_spectrum(image)
        noise_res = compute_noise_residual(image)
        exif_res = analyze_exif(image)

        # 2. Heuristic scoring across IMAGE_LABELS
        # Scores start neutral and accumulate forensic evidence weights
        scores = {lbl: 0.10 for lbl in IMAGE_LABELS}
        evidence: list[Evidence] = []

        # Feature A: AI generation indicators
        ai_gen_signals = 0.0
        if spec_res.peak_anomaly_score > 0.3:
            ai_gen_signals += 0.35
            evidence.append(
                Evidence(
                    kind="metric",
                    description="2D FFT periodic lattice spikes detected",
                    payload={"metric": "peak_anomaly_score", "score": spec_res.peak_anomaly_score},
                )
            )
        if noise_res.kurtosis_anomaly:
            ai_gen_signals += 0.30
            evidence.append(
                Evidence(
                    kind="metric",
                    description="Synthetic noise residual kurtosis anomaly",
                    payload={"metric": "mean_kurtosis", "score": noise_res.mean_kurtosis},
                )
            )
        if exif_res.is_ai_software:
            ai_gen_signals += 0.50
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"AI generation software tag found in metadata: {exif_res.software_tag}",
                    payload={"software": exif_res.software_tag},
                )
            )
        if exif_res.dimension_anomaly:
            ai_gen_signals += 0.20
            evidence.append(
                Evidence(
                    kind="flag",
                    description="Typical generative model dimension (square canvas without camera EXIF)",
                    payload={"dimensions": list(image.size)},
                )
            )

        # Feature B: AI edit / splicing indicators
        ai_edit_signals = 0.0
        if ela_res.high_diff_block_ratio > 0.08:
            ai_edit_signals += 0.40
            evidence.append(
                Evidence(
                    kind="metric",
                    description="High localized ELA compression discrepancy across blocks",
                    payload={
                        "metric": "high_diff_block_ratio",
                        "score": ela_res.high_diff_block_ratio,
                    },
                )
            )
        if ela_res.block_variance > 15.0:
            ai_edit_signals += 0.25
            evidence.append(
                Evidence(
                    kind="metric",
                    description="Elevated ELA block variance",
                    payload={"metric": "block_variance", "score": ela_res.block_variance},
                )
            )
        if exif_res.is_editing_software:
            ai_edit_signals += 0.25
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"Image editing software detected in metadata: {exif_res.software_tag}",
                    payload={"software": exif_res.software_tag},
                )
            )

        # Feature C: Filtered / stylistic adjustments
        filtered_signals = 0.0
        if noise_res.channel_variance_ratio > 3.0:
            filtered_signals += 0.35
        if abs(spec_res.radial_decay_slope + 2.0) > 0.8:
            filtered_signals += 0.25

        # Feature D: Authentic camera signals
        authentic_signals = 0.0
        if exif_res.has_camera_info:
            authentic_signals += 0.45
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"Hardware camera metadata present ({exif_res.camera_make} {exif_res.camera_model})",
                    payload={"make": exif_res.camera_make, "model": exif_res.camera_model},
                )
            )
        if exif_res.has_quantization_tables:
            authentic_signals += 0.20
        if not noise_res.kurtosis_anomaly and ela_res.high_diff_block_ratio < 0.03:
            authentic_signals += 0.35

        scores["ai_generated"] += ai_gen_signals
        scores["ai_edited"] += ai_edit_signals
        scores["filtered"] += filtered_signals
        scores["authentic"] += authentic_signals

        # Normalize probabilities
        total = sum(scores.values())
        label_scores = {k: round(v / total, 4) for k, v in scores.items()}

        # Risk is probability of non-authentic content
        risk = round(1.0 - label_scores["authentic"], 4)

        # Generate forensic anomaly heatmap overlay
        png_b64, max_anomaly = generate_forensic_heatmap(
            image=image,
            ela_amplified_img=ela_res.diff_image,
            noise_residual=noise_res.residual_array,
        )
        evidence.insert(
            0,
            Evidence(
                kind="heatmap",
                description="Forensic anomaly map (ELA + noise residual)",
                payload={"png_b64": png_b64, "max_anomaly": max_anomaly},
            ),
        )

        latency_ms = max(5, int((time.perf_counter() - t0) * 1000))

        return ProviderResult(
            provider_id=self.id,
            ok=True,
            label_scores=label_scores,
            risk=risk,
            evidence=evidence,
            latency_ms=latency_ms,
            model_version="heuristic_v0",
            coverage=list(IMAGE_LABELS),
            error=None,
            validated=False,
        )
