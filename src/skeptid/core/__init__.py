"""Core types, contracts, config, and orchestrator for SKEPTID."""

from skeptid.core.config import SkeptidConfig, load_config
from skeptid.core.fusion import fuse_results
from skeptid.core.interfaces import Provider
from skeptid.core.orchestrator import Orchestrator
from skeptid.core.types import (
    IMAGE_LABELS,
    TEXT_LABELS,
    AnalysisInput,
    Evidence,
    Modality,
    ProviderResult,
    RiskLevel,
    Verdict,
)

__all__ = [
    "IMAGE_LABELS",
    "TEXT_LABELS",
    "AnalysisInput",
    "Evidence",
    "Modality",
    "Orchestrator",
    "Provider",
    "ProviderResult",
    "RiskLevel",
    "SkeptidConfig",
    "Verdict",
    "fuse_results",
    "load_config",
]
