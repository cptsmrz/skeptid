"""Unit tests for the multi-vendor External Provider router and failover mechanism."""

import pytest

from skeptid.core.types import AnalysisInput, Modality
from skeptid.providers.external import (
    BaseVendorAdapter,
    ExternalProvider,
)


class FakeVendorAdapter(BaseVendorAdapter):
    """Controllable test vendor adapter for router failover testing."""

    def __init__(
        self,
        name: str,
        model_name: str,
        should_succeed: bool = True,
        response_data: dict | None = None,
        configured: bool = True,
        error_message: str = "Fake network failure",
    ) -> None:
        super().__init__(name=name, model_name=model_name)
        self._configured = configured
        self._should_succeed = should_succeed
        self._response_data = response_data or {
            "label": "phishing",
            "risk": 0.88,
            "confidence": 0.90,
            "reason": f"Synthetic response from {name}",
        }
        self._error_message = error_message
        self.call_count = 0

    def is_configured(self) -> bool:
        return self._configured

    def _to_vendor_request(self, text: str):
        return "http://fake.api", {}, {"text": text}

    def _from_vendor_response(self, response_json: dict):
        return response_json

    async def call_api(self, client, text: str, *args, **kwargs):
        self.call_count += 1
        if not self._should_succeed:
            self.circuit_breaker.record_failure(self.name)
            raise RuntimeError(self._error_message)
        self.circuit_breaker.record_success(self.name)
        return self._response_data


@pytest.mark.asyncio
async def test_external_provider_mock_mode():
    """Verify deterministic mock response when in mock mode."""
    provider = ExternalProvider(is_mock=True)
    res = await provider.analyze(AnalysisInput(modality=Modality.TEXT, text="Suspicious wire transfer request"))
    assert res.ok
    assert res.model_version == "mock"
    assert res.provider_id == "external"
    assert "safe" in res.label_scores


@pytest.mark.asyncio
async def test_external_provider_primary_vendor_success():
    """Verify router uses the first configured vendor when it succeeds."""
    gemini = FakeVendorAdapter("gemini", "gemini-1.5-flash", should_succeed=True)
    groq = FakeVendorAdapter("groq", "llama-3.3-70b-versatile", should_succeed=True)
    provider = ExternalProvider(adapters=[gemini, groq], is_mock=False)

    payload = AnalysisInput(modality=Modality.TEXT, text="Verify your bank details")
    res = await provider.analyze(payload)

    assert res.ok
    assert res.model_version == "gemini:gemini-1.5-flash"
    assert res.risk == 0.88
    assert res.label_scores["phishing"] >= 0.50
    assert gemini.call_count == 1
    assert groq.call_count == 0  # Groq should not be called since Gemini succeeded


@pytest.mark.asyncio
async def test_external_provider_failover_to_secondary():
    """Verify router fails over to second vendor when the first throws an exception."""
    gemini = FakeVendorAdapter("gemini", "gemini-1.5-flash", should_succeed=False)
    groq = FakeVendorAdapter("groq", "llama-3.3-70b-versatile", should_succeed=True)
    provider = ExternalProvider(adapters=[gemini, groq], is_mock=False)

    payload = AnalysisInput(modality=Modality.TEXT, text="Verify your bank details")
    res = await provider.analyze(payload)

    assert res.ok
    assert res.model_version == "groq:llama-3.3-70b-versatile"
    assert gemini.call_count == 1
    assert groq.call_count == 1


@pytest.mark.asyncio
async def test_external_provider_all_vendors_fail():
    """Verify clean error returned when all vendors in router fail."""
    gemini = FakeVendorAdapter("gemini", "gemini-1.5-flash", should_succeed=False)
    groq = FakeVendorAdapter("groq", "llama-3.3-70b-versatile", should_succeed=False)
    provider = ExternalProvider(adapters=[gemini, groq], is_mock=False)

    payload = AnalysisInput(modality=Modality.TEXT, text="Test payload")
    res = await provider.analyze(payload)

    assert not res.ok
    assert "All external vendors failed" in (res.error or "")
    assert res.model_version == "external:all_vendors_failed"


@pytest.mark.asyncio
async def test_external_provider_safety_blocked_handling():
    """Verify safety block returns ok=False, error='blocked'."""
    gemini = FakeVendorAdapter(
        "gemini",
        "gemini-1.5-flash",
        should_succeed=True,
        response_data={"blocked": True, "error": "blocked: SAFETY"},
    )
    provider = ExternalProvider(adapters=[gemini], is_mock=False)

    payload = AnalysisInput(modality=Modality.TEXT, text="Content triggering safety filters")
    res = await provider.analyze(payload)

    assert not res.ok
    assert res.error == "blocked"
    assert res.model_version == "gemini:gemini-1.5-flash"


@pytest.mark.asyncio
async def test_external_provider_sha256_caching():
    """Verify identical text is served from cache with :cached model_version tag."""
    adapter = FakeVendorAdapter("gemini", "gemini-1.5-flash", should_succeed=True)
    provider = ExternalProvider(adapters=[adapter], is_mock=False)

    payload = AnalysisInput(modality=Modality.TEXT, text="Repeated test message")
    res1 = await provider.analyze(payload)
    assert res1.ok
    assert adapter.call_count == 1

    res2 = await provider.analyze(payload)
    assert res2.ok
    assert res2.model_version == "gemini:gemini-1.5-flash:cached"
    assert adapter.call_count == 1  # Not called again due to SHA-256 cache


@pytest.mark.asyncio
async def test_external_provider_budget_exhaustion():
    """Verify daily budget limit halts external API calls."""
    adapter = FakeVendorAdapter("gemini", "gemini-1.5-flash", should_succeed=True)
    provider = ExternalProvider(adapters=[adapter], daily_budget=1, is_mock=False)

    payload1 = AnalysisInput(modality=Modality.TEXT, text="Message 1")
    res1 = await provider.analyze(payload1)
    assert res1.ok

    payload2 = AnalysisInput(modality=Modality.TEXT, text="Message 2")
    res2 = await provider.analyze(payload2)
    assert not res2.ok
    assert "budget" in (res2.error or "").lower()


@pytest.mark.asyncio
async def test_external_provider_per_vendor_budget():
    """Verify per-vendor budget limits calls per vendor adapter."""
    v1 = FakeVendorAdapter("gemini", "gemini-3.8-flash", should_succeed=True)
    v2 = FakeVendorAdapter("groq", "qwen/qwen3.8-27b", should_succeed=True)
    provider = ExternalProvider(adapters=[v1, v2], daily_budget=1, is_mock=False)

    # First call uses v1
    res1 = await provider.analyze(AnalysisInput(modality=Modality.TEXT, text="Call 1"))
    assert res1.ok
    assert v1.call_count == 1
    assert v2.call_count == 0

    # Second call exhausts v1's budget (1) and fails over to v2
    res2 = await provider.analyze(AnalysisInput(modality=Modality.TEXT, text="Call 2"))
    assert res2.ok
    assert v1.call_count == 1
    assert v2.call_count == 1
    assert res2.model_version.startswith("groq")


@pytest.mark.asyncio
async def test_orchestrator_use_external_flag():
    """Verify use_external flag controls external provider execution and external_used verdict field."""
    from skeptid.core.orchestrator import Orchestrator

    orchestrator = Orchestrator()

    # Default use_external=True
    inp_default = AnalysisInput(modality=Modality.TEXT, text="Test email content", use_external=True)
    v1 = await orchestrator.analyze(inp_default)
    p_ids = [p["id"] for p in v1.providers]
    assert "external" in p_ids
    assert v1.external_used is True

    # Disabled use_external=False
    inp_disabled = AnalysisInput(modality=Modality.TEXT, text="Test email content", use_external=False)
    v2 = await orchestrator.analyze(inp_disabled)
    p_ids_disabled = [p["id"] for p in v2.providers]
    assert "external" not in p_ids_disabled
    assert v2.external_used is False


@pytest.mark.asyncio
async def test_external_used_true_on_vendor_failure():
    """SPEC 6.5: external_used is true whenever content was sent to a vendor, even if the call failed.

    This ensures the privacy disclosure is shown whenever an attempt was made
    to send data to an external vendor, regardless of the outcome.
    """
    from skeptid.core.fusion import fuse_results
    from skeptid.core.types import Modality, ProviderResult

    # Simulate an external provider that attempted a call but failed
    failed_external = ProviderResult(
        provider_id="external",
        ok=False,
        label_scores={},
        risk=0.0,
        evidence=[],
        latency_ms=150,
        model_version="gemini:gemini-3.8-flash",  # not "mock" or "budget_exceeded" — a real attempt
        error="Vendor timeout after 8s",
    )
    own_result = ProviderResult(
        provider_id="own",
        ok=True,
        label_scores={"safe": 0.1, "phishing": 0.8, "spam": 0.05, "threat": 0.03, "bullying": 0.02},
        risk=0.90,
        evidence=[],
        latency_ms=30,
        model_version="text_v1",
        coverage=["safe", "phishing", "spam", "threat", "bullying"],
    )

    verdict = fuse_results(
        displayed=own_result,
        all_results=[own_result, failed_external],
        modality=Modality.TEXT,
    )

    assert verdict.external_used is True, (
        "external_used must be True when content was sent to a vendor, even if the call failed"
    )


@pytest.mark.asyncio
async def test_external_used_true_on_safety_block():
    """SPEC 6.5: external_used is true when content is sent and the vendor blocks the request.

    A blocked response means content WAS sent (and received a refusal). The privacy
    disclosure must still appear.
    """
    from skeptid.core.fusion import fuse_results
    from skeptid.core.types import Modality, ProviderResult

    blocked_external = ProviderResult(
        provider_id="external",
        ok=False,
        label_scores={},
        risk=0.0,
        evidence=[],
        latency_ms=200,
        model_version="gemini:gemini-3.8-flash",  # real vendor, not mock
        error="blocked",
    )
    own_result = ProviderResult(
        provider_id="own",
        ok=True,
        label_scores={"safe": 0.05, "phishing": 0.9, "spam": 0.02, "threat": 0.02, "bullying": 0.01},
        risk=0.95,
        evidence=[],
        latency_ms=25,
        model_version="text_v1",
        coverage=["safe", "phishing", "spam", "threat", "bullying"],
    )

    verdict = fuse_results(
        displayed=own_result,
        all_results=[own_result, blocked_external],
        modality=Modality.TEXT,
    )

    assert verdict.external_used is True, (
        "external_used must be True when content was sent and the vendor issued a safety block"
    )


@pytest.mark.asyncio
async def test_external_used_false_when_budget_exceeded():
    """SPEC 6.5: external_used is false when budget exceeded means nothing was sent.

    Budget exhaustion prevents the HTTP call from being made, so the content
    never left the server.
    """
    from skeptid.core.fusion import fuse_results
    from skeptid.core.types import Modality, ProviderResult

    budget_exceeded_result = ProviderResult(
        provider_id="external",
        ok=False,
        label_scores={},
        risk=0.0,
        evidence=[],
        latency_ms=0,
        model_version="external:budget_exceeded",
        error="Daily external call budget exceeded",
    )
    own_result = ProviderResult(
        provider_id="own",
        ok=True,
        label_scores={"safe": 0.8, "phishing": 0.1, "spam": 0.05, "threat": 0.03, "bullying": 0.02},
        risk=0.20,
        evidence=[],
        latency_ms=22,
        model_version="text_v1",
        coverage=["safe", "phishing", "spam", "threat", "bullying"],
    )

    verdict = fuse_results(
        displayed=own_result,
        all_results=[own_result, budget_exceeded_result],
        modality=Modality.TEXT,
    )

    assert verdict.external_used is False, (
        "external_used must be False when budget_exceeded means nothing left the server"
    )

