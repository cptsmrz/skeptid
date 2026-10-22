"""Baseline text model training pipeline.

Trains a pure-Python TF-IDF (word 1-2 grams + char 3-5 grams) + Logistic Regression
classifier with class-weight balancing and explainable n-gram coefficients.
Saves model bundle to models/text_v1.joblib.
"""

import csv
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import joblib

TRAIN_FILE = Path("data/processed/text_train.csv")
VAL_FILE = Path("data/processed/text_val.csv")
MODELS_DIR = Path("models")
MODEL_OUT = MODELS_DIR / "text_v1.joblib"


def tokenize_words(text: str) -> list[str]:
    """Tokenize words into lower-case tokens."""
    return re.findall(r"\b[a-zA-Z0-9_']+\b", text.lower())


def extract_ngrams(text: str) -> list[str]:
    """Extract word (1-2) and character (3-5) n-grams."""
    words = tokenize_words(text)
    ngrams: list[str] = []

    # Word unigrams and bigrams
    for i in range(len(words)):
        ngrams.append(f"w:{words[i]}")
        if i + 1 < len(words):
            ngrams.append(f"w:{words[i]}_{words[i+1]}")

    # Character n-grams (3-5) with boundary markers
    norm = f" {text.lower()} "
    for n in (3, 4, 5):
        for i in range(len(norm) - n + 1):
            ngrams.append(f"c:{norm[i:i+n]}")

    return ngrams


class TfidfVectorizerPure:
    """Pure-Python TF-IDF vectorizer with sublinear scaling and L2 normalization."""

    def __init__(self, max_features: int = 15000, min_df: int = 2) -> None:
        self.max_features = max_features
        self.min_df = min_df
        self.vocab: dict[str, int] = {}
        self.idfs: list[float] = []

    def fit(self, texts: list[str]) -> "TfidfVectorizerPure":
        doc_counts: Counter[str] = Counter()
        n_docs = len(texts)

        for text in texts:
            unique_ngrams = set(extract_ngrams(text))
            doc_counts.update(unique_ngrams)

        # Filter by min_df and select top max_features
        valid = [
            (term, count) for term, count in doc_counts.items() if count >= self.min_df
        ]
        valid.sort(key=lambda x: x[1], reverse=True)
        top_terms = valid[: self.max_features]

        self.vocab = {term: idx for idx, (term, _) in enumerate(top_terms)}
        self.idfs = [0.0] * len(self.vocab)

        for term, idx in self.vocab.items():
            df = doc_counts[term]
            self.idfs[idx] = math.log((1 + n_docs) / (1 + df)) + 1.0

        return self

    def transform(self, text: str) -> dict[int, float]:
        """Convert text into sparse L2-normalized TF-IDF vector."""
        ngrams = extract_ngrams(text)
        counts = Counter(ngrams)
        sparse_vec: dict[int, float] = {}

        for term, count in counts.items():
            idx = self.vocab.get(term)
            if idx is not None:
                # Sublinear TF: 1 + log(tf)
                tf = 1.0 + math.log(count)
                sparse_vec[idx] = tf * self.idfs[idx]

        # L2 normalize
        norm = math.sqrt(sum(val * val for val in sparse_vec.values()))
        if norm > 0:
            for idx in sparse_vec:
                sparse_vec[idx] /= norm

        return sparse_vec


class LogisticRegressionPure:
    """Multi-class Logistic Regression with class weighting and SGD optimization."""

    def __init__(
        self,
        learning_rate: float = 0.2,
        epochs: int = 25,
        l2_reg: float = 1e-4,
    ) -> None:
        self.lr = learning_rate
        self.epochs = epochs
        self.l2 = l2_reg
        self.classes: list[str] = []
        self.weights: dict[str, list[float]] = {}
        self.biases: dict[str, float] = {}

    def fit(
        self,
        x_sparse: list[dict[int, float]],
        y: list[str],
        vocab_size: int,
    ) -> "LogisticRegressionPure":
        self.classes = sorted(set(y))
        n_samples = len(y)
        counts = Counter(y)

        # Class weights: total / (num_classes * count)
        n_classes = len(self.classes)
        class_weights = {
            cls: n_samples / (n_classes * counts[cls]) for cls in self.classes
        }

        # Initialize weights and biases
        self.weights = {cls: [0.0] * vocab_size for cls in self.classes}
        self.biases = {cls: 0.0 for cls in self.classes}

        indices = list(range(n_samples))
        for epoch in range(1, self.epochs + 1):
            lr = self.lr / (1.0 + 0.05 * epoch)
            loss_total = 0.0

            for i in indices:
                features = x_sparse[i]
                target_cls = y[i]
                w_sample = class_weights[target_cls]

                # Compute logits: z_c = bias_c + sum(w_cj * x_j)
                logits: dict[str, float] = {}
                max_logit = -1e9
                for cls in self.classes:
                    z = self.biases[cls]
                    w = self.weights[cls]
                    for feat_idx, feat_val in features.items():
                        z += w[feat_idx] * feat_val
                    logits[cls] = z
                    max_logit = max(max_logit, z)

                # Softmax
                exp_sum = sum(math.exp(z - max_logit) for z in logits.values())
                probs = {
                    cls: math.exp(logits[cls] - max_logit) / exp_sum
                    for cls in self.classes
                }

                # Cross-entropy loss
                p_target = max(1e-12, probs[target_cls])
                loss_total += -math.log(p_target) * w_sample

                # Gradient step
                for cls in self.classes:
                    grad = (probs[cls] - (1.0 if cls == target_cls else 0.0)) * w_sample
                    self.biases[cls] -= lr * grad
                    w_cls = self.weights[cls]
                    for feat_idx, feat_val in features.items():
                        # L2 weight decay + data gradient
                        w_cls[feat_idx] -= lr * (grad * feat_val + self.l2 * w_cls[feat_idx])

        return self

    def predict_proba(self, sparse_vec: dict[int, float]) -> dict[str, float]:
        """Compute calibrated softmax probabilities for an input vector."""
        logits: dict[str, float] = {}
        max_logit = -1e9
        for cls in self.classes:
            z = self.biases[cls]
            w = self.weights[cls]
            for feat_idx, feat_val in sparse_vec.items():
                z += w[feat_idx] * feat_val
            logits[cls] = z
            max_logit = max(max_logit, z)

        exp_sum = sum(math.exp(z - max_logit) for z in logits.values())
        return {
            cls: round(math.exp(logits[cls] - max_logit) / exp_sum, 4)
            for cls in self.classes
        }


def load_dataset_csv(path: Path) -> tuple[list[str], list[str]]:
    """Load text and label arrays from CSV."""
    texts: list[str] = []
    labels: list[str] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("text") or "").strip()
            lbl = (row.get("label") or "").strip()
            if t and lbl:
                texts.append(t)
                labels.append(lbl)
    return texts, labels


def train_model() -> Path:
    """Train the baseline text model and serialize to models/text_v1.joblib."""
    if not TRAIN_FILE.exists():
        raise FileNotFoundError(
            f"Train file not found at {TRAIN_FILE}. Run prepare_text first."
        )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[train_text] Loading training data from {TRAIN_FILE}...")
    x_train_raw, y_train = load_dataset_csv(TRAIN_FILE)
    print(f"[train_text] Loaded {len(x_train_raw)} training examples.")

    print("[train_text] Fitting TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizerPure(max_features=12000, min_df=2)
    vectorizer.fit(x_train_raw)
    vocab_size = len(vectorizer.vocab)
    print(f"[train_text] Vocabulary size: {vocab_size} n-grams.")

    print("[train_text] Transforming training texts...")
    x_train_sparse = [vectorizer.transform(t) for t in x_train_raw]

    print("[train_text] Training Logistic Regression classifier (balanced class weights)...")
    clf = LogisticRegressionPure(learning_rate=0.25, epochs=20, l2_reg=1e-4)
    clf.fit(x_train_sparse, y_train, vocab_size=vocab_size)

    # Validate on val set if present
    if VAL_FILE.exists():
        x_val_raw, y_val = load_dataset_csv(VAL_FILE)
        correct = 0
        for text, true_lbl in zip(x_val_raw, y_val):
            probs = clf.predict_proba(vectorizer.transform(text))
            pred_lbl = max(probs, key=probs.get)  # type: ignore[arg-type]
            if pred_lbl == true_lbl:
                correct += 1
        val_acc = correct / len(y_val) if y_val else 0.0
        print(f"[train_text] Validation Accuracy on {len(y_val)} examples: {val_acc:.4f}")

    # Build model artifact bundle
    bundle: dict[str, Any] = {
        "version": "text_v1",
        "vectorizer": {
            "vocab": vectorizer.vocab,
            "idfs": vectorizer.idfs,
            "max_features": vectorizer.max_features,
            "min_df": vectorizer.min_df,
        },
        "classifier": {
            "classes": clf.classes,
            "weights": clf.weights,
            "biases": clf.biases,
        },
    }

    joblib.dump(bundle, MODEL_OUT)
    print(f"[train_text] Successfully saved model bundle to {MODEL_OUT}")
    return MODEL_OUT


if __name__ == "__main__":
    train_model()
