"""Holdout evaluation pipeline for text models.

Evaluates candidate model on the frozen holdout dataset (data/holdout/text_holdout.csv).
Computes accuracy, macro-F1, per-class precision/recall/F1, confusion matrix,
and detects missing classes. Writes evaluation metrics into models/registry.json.
"""

import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, ".")
sys.path.insert(0, "src")

import joblib

from skeptid.core.types import TEXT_LABELS

HOLDOUT_FILE_V2 = Path("data/holdout/text_holdout_v2.csv")
HOLDOUT_FILE_V1 = Path("data/holdout/text_holdout_v1.csv")
HOLDOUT_FILE = (
    HOLDOUT_FILE_V2
    if HOLDOUT_FILE_V2.exists()
    else (HOLDOUT_FILE_V1 if HOLDOUT_FILE_V1.exists() else Path("data/holdout/text_holdout.csv"))
)
HOLDOUT_VERSION = "holdout_v2" if HOLDOUT_FILE == HOLDOUT_FILE_V2 else "holdout_v1"
MODEL_PATH = Path("models/text_v1.joblib")
REGISTRY_PATH = Path("models/registry.json")


def load_holdout_data() -> tuple[list[str], list[str], list[str], str]:
    """Load text, labels, sources, and SHA-256 from frozen holdout dataset."""
    if not HOLDOUT_FILE.exists():
        raise FileNotFoundError(
            f"Holdout file not found at {HOLDOUT_FILE}. Run prepare_text first."
        )

    file_bytes = HOLDOUT_FILE.read_bytes()
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    texts: list[str] = []
    labels: list[str] = []
    sources: list[str] = []
    with open(HOLDOUT_FILE, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("text") or "").strip()
            lbl = (row.get("label") or "").strip()
            src = (row.get("source") or "unknown").strip()
            if t and lbl:
                texts.append(t)
                labels.append(lbl)
                sources.append(src)
    return texts, labels, sources, sha256_hash


def transform_text_with_bundle(text: str, vectorizer_bundle: dict[str, Any]) -> dict[int, float]:
    """Transform text using serialized vectorizer configuration."""
    vocab: dict[str, int] = vectorizer_bundle["vocab"]
    idfs: list[float] = vectorizer_bundle["idfs"]

    # Extract word and char n-grams matching train_text.py and own_text.py
    words = re.findall(r"\b[a-zA-Z0-9_']+\b", text.lower())
    ngrams: list[str] = []
    for i in range(len(words)):
        ngrams.append(f"w:{words[i]}")
        if i + 1 < len(words):
            ngrams.append(f"w:{words[i]}_{words[i + 1]}")

    norm = f" {text.lower()} "
    for n in (3, 4, 5):
        for i in range(len(norm) - n + 1):
            ngrams.append(f"c:{norm[i : i + n]}")

    counts = Counter(ngrams)
    sparse_vec: dict[int, float] = {}
    for term, count in counts.items():
        idx = vocab.get(term)
        if idx is not None:
            tf = 1.0 + math.log(count)
            sparse_vec[idx] = tf * idfs[idx]

    norm_val = math.sqrt(sum(v * v for v in sparse_vec.values()))
    if norm_val > 0:
        for idx in sparse_vec:
            sparse_vec[idx] /= norm_val

    return sparse_vec


def predict_proba_with_bundle(
    sparse_vec: dict[int, float],
    classifier_bundle: dict[str, Any],
) -> dict[str, float]:
    """Compute class probabilities using serialized classifier configuration."""
    classes: list[str] = classifier_bundle["classes"]
    weights: dict[str, list[float]] = classifier_bundle["weights"]
    biases: dict[str, float] = classifier_bundle["biases"]

    logits: dict[str, float] = {}
    max_logit = -1e9
    for cls in classes:
        z = biases[cls]
        w = weights[cls]
        for idx, val in sparse_vec.items():
            z += w[idx] * val
        logits[cls] = z
        max_logit = max(max_logit, z)

    exp_sum = sum(math.exp(z - max_logit) for z in logits.values())
    return {cls: math.exp(logits[cls] - max_logit) / exp_sum for cls in classes}


def evaluate_model() -> dict[str, Any]:
    """Execute evaluation on frozen holdout and write to registry.json."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found at {MODEL_PATH}. Run train_text first.")

    bundle = joblib.load(MODEL_PATH)
    vec_bundle = bundle["vectorizer"]
    clf_bundle = bundle["classifier"]
    version = bundle.get("version", "text_v1")

    x_holdout, y_true, sources, sha256_hash = load_holdout_data()
    n_total = len(y_true)
    print(
        f"[evaluate] Evaluating {version} on {n_total} frozen holdout samples ({HOLDOUT_FILE.name}, {HOLDOUT_VERSION})..."
    )

    y_pred: list[str] = []
    for text in x_holdout:
        feat = transform_text_with_bundle(text, vec_bundle)
        probs = predict_proba_with_bundle(feat, clf_bundle)
        pred_label = max(probs, key=probs.get)  # type: ignore[arg-type]
        y_pred.append(pred_label)

    # Calculate accuracy
    correct = sum(1 for yt, yp in zip(y_true, y_pred) if yt == yp)
    accuracy = round(correct / n_total, 4) if n_total > 0 else 0.0

    # Per-class metrics
    present_holdout_classes = sorted(set(y_true))
    per_class: dict[str, dict[str, float]] = {}
    f1_list: list[float] = []

    for cls in present_holdout_classes:
        tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp == cls)
        fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt != cls and yp == cls)
        fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == cls and yp != cls)
        support = sum(1 for yt in y_true if yt == cls)

        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
        f1 = (
            round(2 * precision * recall / (precision + recall), 4)
            if (precision + recall) > 0
            else 0.0
        )

        per_class[cls] = {
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "support": support,
        }
        f1_list.append(f1)

    macro_f1 = round(sum(f1_list) / len(f1_list), 4) if f1_list else 0.0

    # Missing classes: classes in TEXT_LABELS absent from holdout
    missing_classes = [lbl for lbl in TEXT_LABELS if lbl not in present_holdout_classes]

    # Confusion matrix
    conf_matrix: dict[str, dict[str, int]] = {
        true_lbl: {pred_lbl: 0 for pred_lbl in present_holdout_classes}
        for true_lbl in present_holdout_classes
    }
    for yt, yp in zip(y_true, y_pred):
        if yt in conf_matrix and yp in conf_matrix[yt]:
            conf_matrix[yt][yp] += 1

    # Promotion gate rule:
    # 1. No missing classes (full coverage of TEXT_LABELS)
    # 2. macro_f1 >= 0.90
    # 3. per-class recall >= 0.80
    gate_reasons: list[str] = []
    if missing_classes:
        gate_reasons.append(f"Missing classes from dataset: {missing_classes}")
    if macro_f1 < 0.90:
        gate_reasons.append(f"Macro-F1 {macro_f1} < 0.90")
    for cls, metrics in per_class.items():
        if metrics["recall"] < 0.80:
            gate_reasons.append(f"Class '{cls}' recall {metrics['recall']} < 0.80")

    gate_met = len(gate_reasons) == 0

    # Evaluate 20-email probe (fixtures/emails.py)
    probe_correct = 0
    probe_details: list[dict[str, Any]] = []
    try:
        from tests.fixtures.emails import FIXTURES

        for item in FIXTURES:
            feat = transform_text_with_bundle(item["text"], vec_bundle)
            probs = predict_proba_with_bundle(feat, clf_bundle)
            pred_label = max(probs, key=probs.get)  # type: ignore[arg-type]
            is_ok = pred_label == item["label"]
            if is_ok:
                probe_correct += 1
            probe_details.append(
                {
                    "id": item["id"],
                    "truth": item["label"],
                    "predicted": pred_label,
                    "confidence": round(probs[pred_label], 4),
                    "correct": is_ok,
                }
            )
    except ImportError as e:
        print(f"[evaluate] Notice: Could not import email fixtures: {e}")

    probe_record: dict[str, Any] = {
        "correct": probe_correct,
        "total": len(probe_details),
        "accuracy": round(probe_correct / len(probe_details), 4) if probe_details else 0.0,
        "details": probe_details,
    }

    evaluation_record: dict[str, Any] = {
        "modality": "text",
        "evaluated_at": datetime.now(UTC).isoformat(),
        "holdout_version": HOLDOUT_VERSION,
        "holdout_samples": n_total,
        "coverage": present_holdout_classes,
        "metrics": {
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "per_class": per_class,
            "confusion_matrix": conf_matrix,
        },
        "probe_20_email": probe_record,
        "missing_classes": missing_classes,
        "gate_met": gate_met,
        "gate_reasons": gate_reasons,
    }

    print("\n--- Model Evaluation Summary ---")
    print(f"Model Version: {version}")
    print(f"Holdout: {HOLDOUT_VERSION} (SHA-256: {sha256_hash[:12]}...)")
    print(f"Accuracy: {accuracy:.4f}")
    print(f"Macro-F1: {macro_f1:.4f}")
    print("Per-class Metrics:")
    for cls, m in per_class.items():
        print(
            f"  [{cls}] Precision: {m['precision']:.4f}, Recall: {m['recall']:.4f}, F1: {m['f1_score']:.4f}, Support: {m['support']}"
        )
    print(f"Coverage: {present_holdout_classes}")
    print(f"Missing Classes: {missing_classes}")
    print(f"Promotion Gate Status: {'MET' if gate_met else 'REFUSED'}")
    if gate_reasons:
        for r in gate_reasons:
            print(f"  Reason: {r}")

    if probe_details:
        print(
            f"\n--- 20-Email Probe: {probe_correct}/{len(probe_details)} correct ({probe_record['accuracy'] * 100:.1f}%) ---"
        )
        for p in probe_details:
            status_tag = "OK" if p["correct"] else "WRONG"
            print(
                f"  {p['id']:<8} truth={p['truth']:<10} pred={p['predicted']:<10} conf={p['confidence']:.3f} [{status_tag}]"
            )
    print("--------------------------------\n")

    # Update models/registry.json
    registry_data: dict[str, Any] = {"models": {}, "promotions": []}
    if REGISTRY_PATH.exists():
        try:
            with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
                registry_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            registry_data = {"models": {}, "promotions": []}

    # Record holdout metadata in registry
    registry_data["holdout"] = {
        "version": HOLDOUT_VERSION,
        "filename": HOLDOUT_FILE.name,
        "sha256": sha256_hash,
        "seed": 42,
        "sources": sorted(set(sources)),
        "samples": n_total,
    }

    registry_data.setdefault("models", {})[version] = evaluation_record

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry_data, f, indent=2)
    print(f"[evaluate] Successfully recorded metrics and holdout metadata to {REGISTRY_PATH}")

    return evaluation_record


if __name__ == "__main__":
    evaluate_model()
