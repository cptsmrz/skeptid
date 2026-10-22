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
