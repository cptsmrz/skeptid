"""Model registry inspection and gated promotion engine.

Enforces strict promotion gates from holdout metrics before changing primary providers
in config/skeptid.yaml. Refuses promotion if any modality classes are missing.
CLI: python -m skeptid.training.registry promote --modality text
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from skeptid.core.types import IMAGE_LABELS, TEXT_LABELS

REGISTRY_PATH = Path("models/registry.json")
CONFIG_PATH = Path("config/skeptid.yaml")


class GateRefusedError(Exception):
    """Raised when a candidate model fails the metric-gated promotion criteria."""


def load_registry() -> dict[str, Any]:
    """Read data from models/registry.json."""
    if not REGISTRY_PATH.exists():
        return {"models": {}, "promotions": []}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def check_gate(modality: str, version: str | None = None) -> tuple[bool, str, list[str]]:
    """Check whether a model candidate meets the promotion gate.
    
    Returns (gate_met, candidate_version, reasons).
    """
    registry = load_registry()
    models = registry.get("models", {})

    # Find target model version
    candidate_key: str | None = None
    if version:
        if version in models and models[version].get("modality") == modality:
            candidate_key = version
    else:
        # Latest model for this modality
        matching = [
            (k, v) for k, v in models.items() if v.get("modality") == modality
        ]
        if matching:
            candidate_key = matching[-1][0]

    if not candidate_key:
        return False, "", [f"No candidate model found in registry for modality '{modality}'."]

    model_data = models[candidate_key]
    missing = model_data.get("missing_classes", [])
    metrics = model_data.get("metrics", {})
    macro_f1 = metrics.get("macro_f1", 0.0)
    per_class = metrics.get("per_class", {})

    reasons: list[str] = []

    # Hard rule: Gate refuses while coverage is incomplete or any class is missing
    expected_labels = TEXT_LABELS if modality in ("text", "email") else IMAGE_LABELS
    coverage = model_data.get("coverage", [])
    if missing or (coverage and set(coverage) < set(expected_labels)):
        uncovered = missing or list(set(expected_labels) - set(coverage))
        reasons.append(
            f"Coverage incomplete: missing classes {uncovered}. All {len(expected_labels)} classes must be covered before promotion."
        )

    if modality == "text":
        if macro_f1 < 0.90:
            reasons.append(f"Macro-F1 {macro_f1:.4f} is below gate threshold of 0.90")
        for cls, m in per_class.items():
            recall = m.get("recall", 0.0)
            if recall < 0.80:
                reasons.append(f"Class '{cls}' recall {recall:.4f} is below gate threshold of 0.80")

    gate_met = len(reasons) == 0
    return gate_met, candidate_key, reasons


def promote_modality_primary(modality: str, version: str | None = None) -> None:
    """Evaluate candidate and promote to primary in config/skeptid.yaml if gate is met."""
    gate_met, candidate_ver, reasons = check_gate(modality, version)

    if not gate_met:
        print(f"\n[Registry Gate] PROMOTION REFUSED for modality '{modality}' ({candidate_ver}):")
        for r in reasons:
            print(f"  - {r}")
        raise GateRefusedError(f"Gate refused for '{modality}': {'; '.join(reasons)}")

    # Update config/skeptid.yaml
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found at {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    if modality not in cfg:
        cfg[modality] = {}

    prev_primary = cfg[modality].get("primary", "unknown")
    cfg[modality]["primary"] = "own"

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    # Record promotion in models/registry.json
    registry = load_registry()
    promotion_event = {
        "modality": modality,
        "promoted_version": candidate_ver,
        "previous_primary": prev_primary,
        "new_primary": "own",
        "promoted_at": datetime.now(UTC).isoformat(),
    }
    registry.setdefault("promotions", []).append(promotion_event)

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)

    print(
        f"\n[Registry Gate] PROMOTION SUCCESS: '{modality}' primary promoted from '{prev_primary}' to 'own' ({candidate_ver})."
    )


def main() -> int:
    """CLI entrypoint for model registry operations."""
    parser = argparse.ArgumentParser(description="SKEPTID Model Registry & Gate")
    subparsers = parser.add_subparsers(dest="command")

    # promote command
    promote_parser = subparsers.add_parser("promote", help="Promote candidate model to primary")
    promote_parser.add_argument("--modality", required=True, choices=["text", "image", "email", "video"])
    promote_parser.add_argument("--version", required=False, help="Explicit model version to promote")

    # status command
    subparsers.add_parser("status", help="Show registry status and metrics")

    args = parser.parse_args()

    if args.command == "promote":
        try:
            promote_modality_primary(args.modality, args.version)
            return 0
        except GateRefusedError:
            return 1
        except (OSError, yaml.YAMLError, json.JSONDecodeError, ValueError) as exc:
            print(f"Error during promotion: {exc}", file=sys.stderr)
            return 1
    elif args.command == "status":
        reg = load_registry()
        print(json.dumps(reg, indent=2))
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
