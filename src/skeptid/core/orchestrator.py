"""Orchestrator for concurrent provider dispatch, fallback, circuit breaker, and fusion."""

import asyncio
import time
from collections import defaultdict

from skeptid.core.config import SkeptidConfig, load_config
from skeptid.core.fusion import fuse_results
from skeptid.core.interfaces import Provider
from skeptid.core.types import AnalysisInput, Modality, ProviderResult, Verdict
from skeptid.providers.mock import MockProvider


class AllProvidersFailedError(Exception):
    """Raised when all configured providers for a modality fail."""

class CircuitBreaker:
    """In-memory circuit breaker that trips after 3 failures within 60 seconds."""

    def __init__(self, failure_threshold: int = 3, window_seconds: float = 60.0, cooldown_seconds: float = 60.0) -> None:
        self.threshold = failure_threshold
        self.window = window_seconds
        self.cooldown = cooldown_seconds
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._tripped_at: dict[str, float] = {}

    def is_open(self, provider_id: str, now: float | None = None) -> bool:
        """Check if the circuit is currently open/tripped for a provider."""
        t = now if now is not None else time.time()

        # Check if currently in cooldown
        if provider_id in self._tripped_at:
            if t - self._tripped_at[provider_id] < self.cooldown:
                return True
            # Cooldown passed: reset circuit
            del self._tripped_at[provider_id]
            self._failures[provider_id].clear()

        return False

    def record_failure(self, provider_id: str, now: float | None = None) -> None:
        """Record a failure event and trip circuit if threshold reached."""
        t = now if now is not None else time.time()
        # Clean older failures
        history = [ts for ts in self._failures[provider_id] if t - ts <= self.window]
        history.append(t)
        self._failures[provider_id] = history

        if len(history) >= self.threshold:
            self._tripped_at[provider_id] = t

    def record_success(self, provider_id: str) -> None:
        """Clear failures on success if circuit is closed."""
        if provider_id not in self._tripped_at:
            self._failures[provider_id].clear()


class Orchestrator:
    """Dispatches analysis requests across configured providers concurrently."""

    def __init__(
        self,
        config: SkeptidConfig | None = None,
        providers: dict[Modality, dict[str, Provider]] | None = None,
    ) -> None:
        self.config = config or load_config()
        self.circuit_breaker = CircuitBreaker()
        self.providers: dict[Modality, dict[str, Provider]] = defaultdict(dict)

        if providers:
            for mod, p_dict in providers.items():
                self.providers[mod].update(p_dict)
        else:
            self._init_default_providers()

    def _init_default_providers(self) -> None:
        """Initialize default mock providers for all modalities and chains."""
        for modality in Modality:
            if modality == Modality.AUDIO:
                continue
            try:
                mod_cfg = self.config.get_modality_config(modality.value)
                for pid in mod_cfg.chain:
                    self.providers[modality][pid] = MockProvider(
                        provider_id=pid,
                        modality=modality,
                    )
            except ValueError:
                continue

    def register_provider(self, modality: Modality, provider: Provider) -> None:
        """Register or override a provider instance for a modality."""
        self.providers[modality][provider.id] = provider

    async def _run_single_provider(
        self,
        provider: Provider,
        payload: AnalysisInput,
        timeout_s: float,
    ) -> ProviderResult:
        """Execute a single provider with circuit breaker, timeout, and exception safety."""
        pid = provider.id
        now = time.time()

        if self.circuit_breaker.is_open(pid, now):
            return ProviderResult(
                provider_id=pid,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=0,
                model_version="circuit_breaker",
                error=f"Circuit breaker open for {pid} (cooldown active)",
            )

        t0 = time.perf_counter()
        try:
            result = await asyncio.wait_for(provider.analyze(payload), timeout=timeout_s)
            if not result.ok:
                self.circuit_breaker.record_failure(pid)
            else:
                self.circuit_breaker.record_success(pid)
            return result
        except TimeoutError:
            self.circuit_breaker.record_failure(pid)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return ProviderResult(
                provider_id=pid,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=latency_ms,
                model_version="unknown",
                error=f"Timeout after {timeout_s}s",
            )
        except Exception as exc:  # noqa: BLE001
            self.circuit_breaker.record_failure(pid)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            return ProviderResult(
                provider_id=pid,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=latency_ms,
                model_version="unknown",
                error=f"Provider exception: {exc}",
            )

    async def analyze(
        self,
        payload: AnalysisInput,
        analysis_id: str | None = None,
    ) -> Verdict:
        """Dispatch analysis concurrently across configured provider chain and fuse results."""
        modality = payload.modality
        mod_cfg = self.config.get_modality_config(modality.value)

        # Collect configured providers from chain
        chain_ids = mod_cfg.chain
        tasks = []
        for pid in chain_ids:
            provider = self.providers[modality].get(pid)
            if not provider:
                # Dynamically instantiate mock provider if missing
                provider = MockProvider(provider_id=pid, modality=modality)
                self.providers[modality][pid] = provider
            tasks.append(self._run_single_provider(provider, payload, mod_cfg.timeout_s))

        # Run all chain providers concurrently
        results: list[ProviderResult] = await asyncio.gather(*tasks)

        # Select displayed result: first provider in chain order that succeeded (ok=True)
        displayed: ProviderResult | None = None
        for res in results:
            if res.ok:
                displayed = res
                break

        if displayed is None:
            # Rule 4: If all providers fail, return HTTP 503. Never return a fabricated verdict.
            raise AllProvidersFailedError(
                f"All providers failed for modality '{modality.value}' in chain {chain_ids}"
            )

        # Fuse displayed result and shadow results
        return fuse_results(
            displayed=displayed,
            all_results=results,
            modality=modality,
            analysis_id=analysis_id,
            low_max=self.config.thresholds.low_max,
            medium_max=self.config.thresholds.medium_max,
        )
