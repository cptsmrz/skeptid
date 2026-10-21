"""Core data types and contracts for SKEPTID."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class Modality(str, Enum):
    """Supported modalities in SKEPTID."""
    TEXT = "text"
    EMAIL = "email"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"

class RiskLevel(str, Enum):
    """Categorical risk severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

TEXT_LABELS: list[str] = ["safe", "phishing", "spam", "threat", "bullying"]
IMAGE_LABELS: list[str] = ["authentic", "filtered", "ai_edited", "ai_generated"]

@dataclass
class Evidence:
    """Verifiable forensic evidence explaining a detection signal."""
    kind: Literal["span", "heatmap", "frame_score", "metric", "flag"]
    description: str
    payload: dict[str, Any]

@dataclass
class ProviderResult:
    """Result returned by a single provider analysis."""
    provider_id: str  # "external" | "opensource" | "own"
    ok: bool
    label_scores: dict[str, float]  # calibrated probabilities over the modality's labels
    risk: float  # 0..1 = 1 - P(safe/authentic)
    evidence: list[Evidence]
    latency_ms: int
    model_version: str
    error: str | None = None

@dataclass
class AnalysisInput:
    """Input payload to be evaluated by an engine/provider."""
    modality: Modality
    text: str | None = None
    raw_bytes: bytes | None = None
    filename: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class Verdict:
    """Final unified verdict output returned by SKEPTID."""
    id: str
    modality: Modality
    label: str
    risk: float
    level: str
    confidence: float
    disagreement: bool
    primary_provider: str
    mock: bool
    providers: list[dict[str, Any]]
    evidence: list[Evidence]
    limits_note: str = "Risk score with evidence, not proof."
