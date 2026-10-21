"""Pure fusion logic for combining provider signals into risk scores and verdicts."""

import math
import uuid
from typing import Any

from skeptid.core.types import (
    IMAGE_LABELS,
    TEXT_LABELS,
    Modality,
    ProviderResult,
    RiskLevel,
    Verdict,
)


def compute_normalised_entropy(label_scores: dict[str, float]) -> float:
    """Calculate normalized Shannon entropy in [0, 1].
    
    Returns 0.0 when certainty is maximal (1.0 for one class),
    and 1.0 when probabilities are uniformly distributed.
    """
    if not label_scores:
        return 1.0

    valid_probs = [p for p in label_scores.values() if p > 0.0]
    total = sum(valid_probs)
    if total <= 0:
        return 1.0

    # Renormalize to ensure sum is 1.0
    probs = [p / total for p in valid_probs]
    k = len(label_scores)
    if k <= 1:
        return 0.0

    h = -sum(p * math.log2(p) for p in probs)
    max_h = math.log2(k)
    norm_h = h / max_h if max_h > 0 else 0.0
    return max(0.0, min(1.0, norm_h))


def compute_confidence(
    label_scores: dict[str, float],
    disagreement: bool,
    ok_provider_count: int,
) -> float:
    """Compute confidence score [0.0, 1.0] from entropy with uncertainty penalties."""
    norm_entropy = compute_normalised_entropy(label_scores)
    base_conf = 1.0 - norm_entropy

    if disagreement:
        base_conf *= 0.7
    if ok_provider_count <= 1:
        base_conf *= 0.8

    return round(max(0.0, min(1.0, base_conf)), 4)


def classify_risk_level(
    risk: float,
    low_max: float = 0.35,
    medium_max: float = 0.70,
) -> str:
    """Categorize continuous risk score into LOW, MEDIUM, or HIGH."""
    if risk < low_max:
        return RiskLevel.LOW.value
    if risk < medium_max:
        return RiskLevel.MEDIUM.value
    return RiskLevel.HIGH.value


def check_disagreement(ok_results: list[ProviderResult], threshold: float = 0.40) -> bool:
    """Return True if max(risk) - min(risk) > threshold across successful providers."""
    if len(ok_results) < 2:
        return False
    risks = [r.risk for r in ok_results]
    return (max(risks) - min(risks)) > threshold


def fuse_email_components(
    text_risk: float | None = None,
    url_risk: float | None = None,
    header_risk: float | None = None,
    attachment_risk: float | None = None,
) -> float:
    """Combine email components with renormalised weights and floor rule.
    
    Formula: 0.60 text + 0.15 url + 0.15 header + 0.10 attachment
    Floor rule: if any present component >= 0.90, final risk >= 0.80.
    """
    weights = {
        "text": (0.60, text_risk),
        "url": (0.15, url_risk),
        "header": (0.15, header_risk),
        "attachment": (0.10, attachment_risk),
    }
    active_weights: list[float] = []
    active_values: list[float] = []

    for w, val in weights.values():
        if val is not None:
            active_weights.append(w)
            active_values.append(val)

    if not active_weights:
        return 0.0

    total_w = sum(active_weights)
    fused_risk = sum((w / total_w) * val for w, val in zip(active_weights, active_values))

    # Floor rule: if any component >= 0.90, final risk >= 0.80
    if any(val >= 0.90 for val in active_values):
        fused_risk = max(fused_risk, 0.80)

    return round(max(0.0, min(1.0, fused_risk)), 4)


def fuse_results(
    displayed: ProviderResult,
    all_results: list[ProviderResult],
    modality: Modality,
    analysis_id: str | None = None,
    low_max: float = 0.35,
    medium_max: float = 0.70,
) -> Verdict:
    """Fuse provider results into the final Verdict schema."""
    ok_results = [r for r in all_results if r.ok]
    disagreement = check_disagreement(ok_results)

    # Determine dominant label from displayed provider
    scores = displayed.label_scores
    if scores:
        best_label = max(scores, key=scores.get)  # type: ignore[arg-type]
    else:
        best_label = (
            TEXT_LABELS[0] if modality in (Modality.TEXT, Modality.EMAIL) else IMAGE_LABELS[0]
        )

    risk = round(max(0.0, min(1.0, displayed.risk)), 4)
    level = classify_risk_level(risk, low_max=low_max, medium_max=medium_max)
    confidence = compute_confidence(scores, disagreement, len(ok_results))

    # Detect if any provider ran in mock mode
    is_mock = any(r.model_version == "mock" for r in all_results)

    provider_summaries: list[dict[str, Any]] = [
        {
            "id": r.provider_id,
            "ok": r.ok,
            "risk": round(r.risk, 4),
            "model_version": r.model_version,
            "latency_ms": r.latency_ms,
            "error": r.error,
        }
        for r in all_results
    ]

    return Verdict(
        id=analysis_id or str(uuid.uuid4()),
        modality=modality,
        label=best_label,
        risk=risk,
        level=level,
        confidence=confidence,
        disagreement=disagreement,
        primary_provider=displayed.provider_id,
        mock=is_mock,
        providers=provider_summaries,
        evidence=list(displayed.evidence),
        limits_note="Risk score with evidence, not proof.",
    )
