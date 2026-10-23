"""Unit tests for orchestrator: fallback, timeouts, circuit breaker, disagreement, and 503."""

import asyncio

import pytest

from skeptid.core.config import ModalityConfig, SkeptidConfig
from skeptid.core.orchestrator import AllProvidersFailedError, CircuitBreaker, Orchestrator
from skeptid.core.types import AnalysisInput, Modality, ProviderResult
from skeptid.providers.mock import MockProvider


class HangingProvider(MockProvider):
    """Provider that hangs to test timeout handling."""

    async def analyze(self, payload: AnalysisInput) -> ProviderResult:
        await asyncio.sleep(2.0)
        return await super().analyze(payload)


@pytest.mark.asyncio
async def test_fallback_order() -> None:
    # Chain: own, opensource, external
    # own fails -> opensource succeeds and becomes displayed result
    cfg = SkeptidConfig(
        text=ModalityConfig(primary="own", chain=["own", "opensource", "external"], timeout_s=1.0)
    )
    p_own = MockProvider("own", Modality.TEXT, force_error="Database offline")
    p_open = MockProvider("opensource", Modality.TEXT)
    p_ext = MockProvider("external", Modality.TEXT)

    orchestrator = Orchestrator(
        config=cfg,
        providers={Modality.TEXT: {"own": p_own, "opensource": p_open, "external": p_ext}},
    )
    inp = AnalysisInput(modality=Modality.TEXT, text="Test fallback order")

    verdict = await orchestrator.analyze(inp)
    assert verdict.primary_provider == "opensource"
    assert len(verdict.providers) == 3
    # Check that 'own' is recorded as failed in the providers list
    own_res = next(p for p in verdict.providers if p["id"] == "own")
    assert own_res["ok"] is False


@pytest.mark.asyncio
async def test_all_providers_fail_raises_503_error() -> None:
    cfg = SkeptidConfig(
        text=ModalityConfig(primary="own", chain=["own", "opensource"], timeout_s=1.0)
    )
    p_own = MockProvider("own", Modality.TEXT, force_error="Fail 1")
    p_open = MockProvider("opensource", Modality.TEXT, force_error="Fail 2")

    orchestrator = Orchestrator(
        config=cfg, providers={Modality.TEXT: {"own": p_own, "opensource": p_open}}
    )
    inp = AnalysisInput(modality=Modality.TEXT, text="Should fail completely")

    with pytest.raises(AllProvidersFailedError):
        await orchestrator.analyze(inp)


@pytest.mark.asyncio
async def test_provider_timeout_handled() -> None:
    cfg = SkeptidConfig(
        text=ModalityConfig(primary="hanging", chain=["hanging", "fallback"], timeout_s=0.1)
    )
    p_hang = HangingProvider("hanging", Modality.TEXT)
    p_fallback = MockProvider("fallback", Modality.TEXT)

    orchestrator = Orchestrator(
        config=cfg, providers={Modality.TEXT: {"hanging": p_hang, "fallback": p_fallback}}
    )
    inp = AnalysisInput(modality=Modality.TEXT, text="Timeout test")

    verdict = await orchestrator.analyze(inp)
    assert verdict.primary_provider == "fallback"
    hang_res = next(p for p in verdict.providers if p["id"] == "hanging")
    assert hang_res["ok"] is False
    assert "Timeout after" in (hang_res["error"] or "")


@pytest.mark.asyncio
async def test_circuit_breaker_tripping_and_recovery() -> None:
    cb = CircuitBreaker(failure_threshold=3, window_seconds=60.0, cooldown_seconds=0.2)
    assert cb.is_open("p1") is False

    # Record 3 failures
    cb.record_failure("p1")
    cb.record_failure("p1")
    assert cb.is_open("p1") is False
    cb.record_failure("p1")

    # Circuit should now be tripped
    assert cb.is_open("p1") is True

    # Wait for cooldown
    await asyncio.sleep(0.25)
    # Circuit should have reset
    assert cb.is_open("p1") is False


@pytest.mark.asyncio
async def test_orchestrator_disagreement_detection() -> None:
    # Create two providers with differing fixed risk
    class HighRiskProvider(MockProvider):
        async def analyze(self, payload: AnalysisInput) -> ProviderResult:
            res = await super().analyze(payload)
            res.risk = 0.90
            res.label_scores = {"phishing": 0.90, "safe": 0.10}
            return res

    class LowRiskProvider(MockProvider):
        async def analyze(self, payload: AnalysisInput) -> ProviderResult:
            res = await super().analyze(payload)
            res.risk = 0.10
            res.label_scores = {"phishing": 0.10, "safe": 0.90}
            return res

    cfg = SkeptidConfig(
        text=ModalityConfig(primary="p_high", chain=["p_high", "p_low"], timeout_s=1.0)
    )
    orchestrator = Orchestrator(
        config=cfg,
        providers={
            Modality.TEXT: {
                "p_high": HighRiskProvider("p_high", Modality.TEXT),
                "p_low": LowRiskProvider("p_low", Modality.TEXT),
            }
        },
    )
    inp = AnalysisInput(modality=Modality.TEXT, text="Disagreement sample")
    verdict = await orchestrator.analyze(inp)

    # 0.90 - 0.10 = 0.80 > 0.40 -> disagreement is True
    assert verdict.disagreement is True
