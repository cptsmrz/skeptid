"""P2 Open-source text provider adapting Detoxify and OpenTextShield.

Lazy-loads third-party transformer models with clean fallback when optional dependencies
are not installed.
"""

import asyncio
from pathlib import Path
import time
from typing import Any

from skeptid.core.interfaces import Provider
from skeptid.core.types import (
    TEXT_LABELS,
    AnalysisInput,
    Evidence,
    Modality,
    ProviderResult,
)


class OpenSourceTextProvider(Provider):
    """P2 text provider combining Detoxify (threat/bullying) and OpenTextShield (spam/phishing)."""

    def __init__(self, provider_id: str = "opensource") -> None:
        self.id = provider_id
        self.modality = Modality.TEXT
        self._detoxify: Any | None = None
        self._text_shield: Any | None = None
        self._initialized = False

    def _ensure_models(self) -> bool:
        """Attempt lazy loading of optional open source packages."""
        if self._initialized:
            return self._detoxify is not None or self._text_shield is not None

        self._initialized = True
        try:
            from transformers import pipeline  # type: ignore[import-untyped]

            self._detoxify = pipeline(
                "text-classification",
                model="unitary/toxic-bert",
                local_files_only=True,
                top_k=None,
            )
        except (ImportError, ModuleNotFoundError, RuntimeError, ValueError, OSError, Exception):
            self._detoxify = None

        try:
            from transformers import pipeline  # type: ignore[import-untyped]

            self._text_shield = pipeline(
                "text-classification",
                model="telecomsxchange/OpenTextShield",
                local_files_only=True,
                top_k=None,
            )
        except (ImportError, ModuleNotFoundError, RuntimeError, ValueError, OSError, Exception):
            self._text_shield = None

        return self._detoxify is not None or self._text_shield is not None

    async def health(self) -> bool:
        """Health check returns True if at least one model is operational."""
        return self._ensure_models()

    async def analyze(self, payload: AnalysisInput) -> ProviderResult:
        """Execute text analysis using Detoxify and OpenTextShield if installed."""
        t0 = time.perf_counter()
        text = payload.text or ""

        if not await asyncio.to_thread(self._ensure_models):
            # Clean fallback when optional dependencies are absent
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return ProviderResult(
                provider_id=self.id,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=latency_ms,
                model_version="detoxify_textshield_stub",
                coverage=[],
                error="optional_dependency_not_installed",
            )

        label_scores: dict[str, float] = {lbl: 0.0 for lbl in TEXT_LABELS}
        evidence: list[Evidence] = []

        # 1. Detoxify predictions (threat, bullying)
        if self._detoxify is not None:
            try:
                def _run_detox():
                    return (
                        self._detoxify.predict(text)
                        if hasattr(self._detoxify, "predict")
                        else self._detoxify(text[:512])
                    )
                raw = await asyncio.to_thread(_run_detox)
                if isinstance(raw, dict):
                    threat_score = float(raw.get("threat", 0.0))
                    insult_score = float(raw.get("insult", 0.0))
                    severe_score = float(raw.get("severe_toxicity", 0.0))
                    tox_score = float(raw.get("toxicity", 0.0))
                else:
                    items = (
                        raw[0]
                        if isinstance(raw, list) and len(raw) > 0 and isinstance(raw[0], list)
                        else raw
                    )
                    scores = {
                        str(d.get("label", "")).lower(): float(d.get("score", 0.0))
                        for d in items
                        if isinstance(d, dict)
                    }
                    threat_score = scores.get("threat", 0.0)
                    insult_score = scores.get("insult", 0.0)
                    severe_score = scores.get("severe_toxic", scores.get("severe_toxicity", 0.0))
                    tox_score = scores.get("toxic", scores.get("toxicity", 0.0))
                bullying_score = max(insult_score, severe_score, tox_score)

                label_scores["threat"] = round(threat_score, 4)
                label_scores["bullying"] = round(bullying_score, 4)

                if threat_score > 0.4:
                    evidence.append(
                        Evidence(
                            kind="metric",
                            description="Detoxify threat confidence",
                            payload={"metric": "threat", "score": round(threat_score, 3)},
                        )
                    )
                if bullying_score > 0.4:
                    evidence.append(
                        Evidence(
                            kind="metric",
                            description="Detoxify harassment confidence",
                            payload={"metric": "bullying", "score": round(bullying_score, 3)},
                        )
                    )
            except (RuntimeError, ValueError, TypeError):
                label_scores["threat"] = 0.0
                label_scores["bullying"] = 0.0

        # 2. OpenTextShield predictions (spam, phishing, safe)
        if self._text_shield is not None:
            try:
                shield_res = await asyncio.to_thread(self._text_shield, text[:512])
                # shield_res with top_k=None returns list of dicts or list of list of dicts
                scores_list = (
                    shield_res[0]
                    if isinstance(shield_res, list) and isinstance(shield_res[0], list)
                    else shield_res
                )
                for item in scores_list:
                    lbl = str(item.get("label", "")).lower()
                    conf = float(item.get("score", 0.0))
                    if "phish" in lbl:
                        label_scores["phishing"] = round(conf, 4)
                        if conf > 0.4:
                            evidence.append(
                                Evidence(
                                    kind="metric",
                                    description="OpenTextShield phishing confidence",
                                    payload={"metric": "phishing", "score": round(conf, 3)},
                                )
                            )
                    elif "spam" in lbl:
                        label_scores["spam"] = round(conf, 4)
                        if conf > 0.4:
                            evidence.append(
                                Evidence(
                                    kind="metric",
                                    description="OpenTextShield spam confidence",
                                    payload={"metric": "spam", "score": round(conf, 3)},
                                )
                            )
                    elif "ham" in lbl or "legit" in lbl:
                        label_scores["safe"] = round(conf, 4)
            except (RuntimeError, ValueError, TypeError):
                label_scores["phishing"] = 0.0
                label_scores["spam"] = 0.0

        # Calculate safe residual
        max_threat = max(
            label_scores["phishing"],
            label_scores["spam"],
            label_scores["threat"],
            label_scores["bullying"],
        )
        safe_prob = round(max(0.0, 1.0 - max_threat), 4)
        label_scores["safe"] = safe_prob

        # Renormalize to ensure sum is 1.0
        total = sum(label_scores.values())
        if total > 0:
            label_scores = {k: round(v / total, 4) for k, v in label_scores.items()}

        risk = round(1.0 - label_scores.get("safe", 0.5), 4)
        latency_ms = max(5, int((time.perf_counter() - t0) * 1000))

        return ProviderResult(
            provider_id=self.id,
            ok=True,
            label_scores=label_scores,
            risk=risk,
            evidence=evidence,
            latency_ms=latency_ms,
            model_version="detoxify_textshield_v1",
            coverage=list(TEXT_LABELS),
            error=None,
        )
