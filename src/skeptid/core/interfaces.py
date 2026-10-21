"""Protocol definitions and interfaces for SKEPTID providers and engines."""

from typing import Protocol

from skeptid.core.types import AnalysisInput, Modality, ProviderResult


class Provider(Protocol):
    """Interface implemented by every provider across modalities."""
    id: str
    modality: Modality

    async def analyze(self, payload: AnalysisInput) -> ProviderResult:
        """Run analysis on the input payload.
        
        Must never raise exceptions to caller; returns ProviderResult with ok=False on failure.
        """
        ...

    async def health(self) -> bool:
        """Check provider operational health."""
        ...
