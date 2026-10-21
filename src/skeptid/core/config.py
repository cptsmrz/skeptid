"""Configuration loading and validation for SKEPTID."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ModalityConfig:
    """Routing and fallback settings for a specific modality."""
    primary: str
    chain: list[str]
    shadow: bool = True
    timeout_s: float = 8.0
    top_k_to_external: int | None = None

@dataclass
class ThresholdsConfig:
    """Categorical risk score threshold boundaries."""
    low_max: float = 0.35
    medium_max: float = 0.70

@dataclass
class SkeptidConfig:
    """Top-level configuration for SKEPTID runtime."""
    text: ModalityConfig = field(
        default_factory=lambda: ModalityConfig(
            primary="own", chain=["own", "opensource", "external"], shadow=True, timeout_s=8.0
        )
    )
    email: ModalityConfig = field(
        default_factory=lambda: ModalityConfig(
            primary="own", chain=["own", "opensource", "external"], shadow=True, timeout_s=8.0
        )
    )
    image: ModalityConfig = field(
        default_factory=lambda: ModalityConfig(
            primary="external", chain=["external", "opensource", "own"], shadow=True, timeout_s=12.0
        )
    )
    video: ModalityConfig = field(
        default_factory=lambda: ModalityConfig(
            primary="external",
            chain=["external", "opensource", "own"],
            shadow=True,
            timeout_s=12.0,
            top_k_to_external=4,
        )
    )
    mode: str = "mock"  # "mock" | "live"
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)

    def get_modality_config(self, modality_name: str) -> ModalityConfig:
        """Get the ModalityConfig corresponding to a modality name."""
        mod = modality_name.lower()
        if hasattr(self, mod):
            val = getattr(self, mod)
            if isinstance(val, ModalityConfig):
                return val
        raise ValueError(f"Unknown modality config: {modality_name}")


def _parse_modality(raw: dict[str, Any], default_timeout: float = 8.0) -> ModalityConfig:
    return ModalityConfig(
        primary=str(raw.get("primary", "own")),
        chain=list(raw.get("chain", ["own", "opensource", "external"])),
        shadow=bool(raw.get("shadow", True)),
        timeout_s=float(raw.get("timeout_s", default_timeout)),
        top_k_to_external=raw.get("top_k_to_external"),
    )


def load_config(path: str | Path | None = None) -> SkeptidConfig:
    """Load SKEPTID configuration from YAML file or return defaults."""
    config_path = Path(path) if path else Path("config/skeptid.yaml")
    if not config_path.exists():
        return SkeptidConfig()

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    thresholds_data = data.get("thresholds", {})
    thresholds = ThresholdsConfig(
        low_max=float(thresholds_data.get("low_max", 0.35)),
        medium_max=float(thresholds_data.get("medium_max", 0.70)),
    )

    return SkeptidConfig(
        text=_parse_modality(data.get("text", {}), default_timeout=8.0),
        email=_parse_modality(data.get("email", {}), default_timeout=8.0),
        image=_parse_modality(data.get("image", {}), default_timeout=12.0),
        video=_parse_modality(data.get("video", {}), default_timeout=12.0),
        mode=str(data.get("mode", "mock")),
        thresholds=thresholds,
    )
