"""Deterministic mock provider implementation for offline testing."""

import hashlib
import time

from skeptid.core.interfaces import Provider
from skeptid.core.types import (
    IMAGE_LABELS,
    TEXT_LABELS,
    AnalysisInput,
    Evidence,
    Modality,
    ProviderResult,
)


class MockProvider(Provider):
    """Deterministic mock provider for all modalities, seeded by input hash."""

    def __init__(
        self,
        provider_id: str = "mock",
        modality: Modality = Modality.TEXT,
        force_error: str | None = None,
        latency_delay_ms: int = 5,
    ) -> None:
        self.id = provider_id
        self.modality = modality
        self.force_error = force_error
        self.latency_delay_ms = latency_delay_ms

    async def health(self) -> bool:
        """Health check indicator."""
        return self.force_error is None

    async def analyze(self, payload: AnalysisInput) -> ProviderResult:
        """Execute deterministic mock analysis."""
        t0 = time.perf_counter()

        if self.force_error:
            return ProviderResult(
                provider_id=self.id,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=int((time.perf_counter() - t0) * 1000),
                model_version="mock",
                error=self.force_error,
            )

        # Seed pseudo-randomness deterministically from input content and provider id
        seed_data = f"{self.id}:{self.modality.value}:{payload.text or ''}:{payload.filename or ''}"
        if payload.raw_bytes:
            seed_data += f":{hashlib.sha256(payload.raw_bytes).hexdigest()[:16]}"

        digest = hashlib.sha256(seed_data.encode("utf-8")).hexdigest()
        seed_int = int(digest[:8], 16)

        labels = (
            TEXT_LABELS
            if self.modality in (Modality.TEXT, Modality.EMAIL)
            else IMAGE_LABELS
        )

        # Generate deterministic pseudorandom values that sum to 1.0
        raw_vals: list[float] = []
        curr = seed_int
        for _ in range(len(labels)):
            curr = (curr * 1103515245 + 12345) & 0x7FFFFFFF
            raw_vals.append((curr % 1000) + 50.0)

        total = sum(raw_vals)
        label_scores = {
            lbl: round(val / total, 4) for lbl, val in zip(labels, raw_vals)
        }

        # Calculate calibrated risk: 1.0 - safe/authentic
        safe_key = "safe" if "safe" in label_scores else "authentic"
        safe_prob = label_scores.get(safe_key, 0.5)
        risk = round(1.0 - safe_prob, 4)

        # Generate modality-specific mock evidence
        evidence: list[Evidence] = []
        if self.modality in (Modality.TEXT, Modality.EMAIL):
            text_len = len(payload.text or "")
            span_end = min(text_len, max(5, (seed_int % 30) + 10))
            if text_len > 0:
                evidence.append(
                    Evidence(
                        kind="span",
                        description=f"Synthetic flag indicator ({self.id})",
                        payload={"start": 0, "end": span_end, "weight": round(risk, 3)},
                    )
                )
            if risk > 0.5:
                evidence.append(
                    Evidence(
                        kind="flag",
                        description="Deterministic heuristic pattern matched",
                        payload={"rule": "mock_rule_trigger", "score": risk},
                    )
                )
        elif self.modality in (Modality.IMAGE, Modality.VIDEO):
            evidence.append(
                Evidence(
                    kind="heatmap",
                    description="Forensic anomaly map (synthetic)",
                    payload={"png_b64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="},
                )
            )

        latency_ms = max(self.latency_delay_ms, int((time.perf_counter() - t0) * 1000))

        return ProviderResult(
            provider_id=self.id,
            ok=True,
            label_scores=label_scores,
            risk=risk,
            evidence=evidence,
            latency_ms=latency_ms,
            model_version="mock",
            coverage=list(labels),
            error=None,
        )
