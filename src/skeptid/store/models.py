"""Data models for persistence and shadow-mode provider logging."""

from dataclasses import dataclass


@dataclass
class AnalysisRecord:
    """Persistent summary of an analysis verdict."""

    id: str
    modality: str
    label: str
    risk: float
    level: str
    confidence: float
    disagreement: bool
    primary_provider: str
    mock: bool
    created_at: str


@dataclass
class ProviderRunRecord:
    """Shadow-mode log of an individual provider execution."""

    analysis_id: str
    provider_id: str
    ok: bool
    risk: float
    latency_ms: int
    model_version: str
    error: str | None = None
    created_at: str = ""


@dataclass
class FeedbackRecord:
    """User feedback submission tagged source=demo."""

    analysis_id: str
    correct: bool
    true_label: str | None = None
    source: str = "demo"
    created_at: str = ""
