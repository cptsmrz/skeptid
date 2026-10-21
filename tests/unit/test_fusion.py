"""Unit tests for fusion math, entropy, confidence, and email weights."""

import pytest

from skeptid.core.fusion import (
    check_disagreement,
    classify_risk_level,
    compute_confidence,
    compute_normalised_entropy,
    fuse_email_components,
    fuse_results,
)
from skeptid.core.types import Evidence, Modality, ProviderResult, RiskLevel


def test_normalised_entropy() -> None:
    # Pure certainty: entropy is 0.0
    certain = {"safe": 1.0, "phishing": 0.0, "spam": 0.0}
    assert compute_normalised_entropy(certain) == pytest.approx(0.0, abs=1e-4)

    # Uniform distribution: maximum entropy is 1.0
    uniform = {"safe": 0.25, "phishing": 0.25, "spam": 0.25, "threat": 0.25}
    assert compute_normalised_entropy(uniform) == pytest.approx(1.0, abs=1e-4)

    # Empty dict
    assert compute_normalised_entropy({}) == 1.0


def test_confidence_calculation_and_penalties() -> None:
    scores = {"safe": 0.95, "phishing": 0.05}
    # Base confidence with 2 ok providers and no disagreement
    conf_base = compute_confidence(scores, disagreement=False, ok_provider_count=2)
    assert conf_base > 0.6

    # With disagreement: should be scaled by 0.7
    conf_disagreed = compute_confidence(scores, disagreement=True, ok_provider_count=2)
    assert conf_disagreed == pytest.approx(conf_base * 0.7, abs=1e-2)

    # With single ok provider: scaled by 0.8
    conf_single = compute_confidence(scores, disagreement=False, ok_provider_count=1)
    assert conf_single == pytest.approx(conf_base * 0.8, abs=1e-2)


def test_classify_risk_level() -> None:
    assert classify_risk_level(0.10) == RiskLevel.LOW.value
    assert classify_risk_level(0.34) == RiskLevel.LOW.value
    assert classify_risk_level(0.35) == RiskLevel.MEDIUM.value
    assert classify_risk_level(0.69) == RiskLevel.MEDIUM.value
    assert classify_risk_level(0.70) == RiskLevel.HIGH.value
    assert classify_risk_level(0.95) == RiskLevel.HIGH.value


def test_disagreement_threshold() -> None:
    p1 = ProviderResult(provider_id="p1", ok=True, label_scores={}, risk=0.20, evidence=[], latency_ms=10, model_version="m")
    p2 = ProviderResult(provider_id="p2", ok=True, label_scores={}, risk=0.50, evidence=[], latency_ms=10, model_version="m")
    p3 = ProviderResult(provider_id="p3", ok=True, label_scores={}, risk=0.75, evidence=[], latency_ms=10, model_version="m")

    # Spread is 0.50 - 0.20 = 0.30 <= 0.40 -> no disagreement
    assert check_disagreement([p1, p2]) is False
    # Spread is 0.75 - 0.20 = 0.55 > 0.40 -> disagreement!
    assert check_disagreement([p1, p3]) is True
    # Single provider cannot disagree
    assert check_disagreement([p1]) is False


def test_email_component_fusion() -> None:
    # Full components: 0.60 * 0.2 + 0.15 * 0.4 + 0.15 * 0.1 + 0.10 * 0.1 = 0.12 + 0.06 + 0.015 + 0.01 = 0.205
    res = fuse_email_components(text_risk=0.2, url_risk=0.4, header_risk=0.1, attachment_risk=0.1)
    assert res == pytest.approx(0.205, abs=1e-3)

    # Floor rule: any component >= 0.90 forces final risk >= 0.80
    res_floor = fuse_email_components(text_risk=0.1, url_risk=0.95, header_risk=0.0, attachment_risk=None)
    assert res_floor >= 0.80


def test_fuse_results_verdict_construction() -> None:
    displayed = ProviderResult(
        provider_id="own",
        ok=True,
        label_scores={"safe": 0.1, "phishing": 0.9},
        risk=0.9,
        evidence=[Evidence(kind="span", description="test", payload={"start": 0, "end": 5, "weight": 0.9})],
        latency_ms=12,
        model_version="mock",
    )
    shadow = ProviderResult(
        provider_id="opensource",
        ok=True,
        label_scores={"safe": 0.2, "phishing": 0.8},
        risk=0.8,
        evidence=[],
        latency_ms=18,
        model_version="mock",
    )

    verdict = fuse_results(
        displayed=displayed,
        all_results=[displayed, shadow],
        modality=Modality.TEXT,
    )

    assert verdict.label == "phishing"
    assert verdict.risk == 0.9
    assert verdict.level == "HIGH"
    assert verdict.primary_provider == "own"
    assert verdict.mock is True
    assert verdict.disagreement is False
    assert len(verdict.providers) == 2
    assert len(verdict.evidence) == 1
