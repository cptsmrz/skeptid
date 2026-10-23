"""P3 Own text provider with explainable span evidence and lexicon integration."""

import math
import re
import time
from pathlib import Path
from typing import Any

import joblib

from skeptid.core.interfaces import Provider
from skeptid.core.types import (
    AnalysisInput,
    Evidence,
    Modality,
    ProviderResult,
)
from skeptid.forensics.lexicon import scan_lexicon

DEFAULT_MODEL_PATH = Path("models/text_v1.joblib")


class OwnTextProvider(Provider):
    """P3 statistical text classifier with n-gram coefficient span explainability."""

    def __init__(
        self,
        provider_id: str = "own",
        model_path: Path | str = DEFAULT_MODEL_PATH,
    ) -> None:
        self.id = provider_id
        self.modality = Modality.TEXT
        self.model_path = Path(model_path)
        self._bundle: dict[str, Any] | None = None

    def _load_model(self) -> dict[str, Any] | None:
        """Lazy load and cache model bundle."""
        if self._bundle is not None:
            return self._bundle

        if not self.model_path.exists():
            return None

        try:
            self._bundle = joblib.load(self.model_path)
            return self._bundle
        except (OSError, EOFError, ValueError, KeyError):
            return None

    async def health(self) -> bool:
        """Health check verifying model artifact availability."""
        return self._load_model() is not None

    async def analyze(self, payload: AnalysisInput) -> ProviderResult:
        """Analyze text and generate calibrated probabilities and explainable spans."""
        t0 = time.perf_counter()
        text = payload.text or ""

        bundle = self._load_model()
        if bundle is None:
            return ProviderResult(
                provider_id=self.id,
                ok=False,
                label_scores={},
                risk=0.0,
                evidence=[],
                latency_ms=int((time.perf_counter() - t0) * 1000),
                model_version="unknown",
                error="model_not_found",
            )

        version = bundle.get("version", "text_v1")
        vec_bundle = bundle["vectorizer"]
        clf_bundle = bundle["classifier"]

        vocab: dict[str, int] = vec_bundle["vocab"]
        idfs: list[float] = vec_bundle["idfs"]
        classes: list[str] = clf_bundle["classes"]
        weights: dict[str, list[float]] = clf_bundle["weights"]
        biases: dict[str, float] = clf_bundle["biases"]

        # 1. Extract n-grams and construct sparse TF-IDF vector
        words = re.findall(r"\b[a-zA-Z0-9_']+\b", text.lower())
        ngrams: list[tuple[str, str]] = []  # (ngram_key, raw_substring)
        for i in range(len(words)):
            ngrams.append((f"w:{words[i]}", words[i]))
            if i + 1 < len(words):
                ngrams.append((f"w:{words[i]}_{words[i + 1]}", f"{words[i]} {words[i + 1]}"))

        norm = f" {text.lower()} "
        for n in (3, 4, 5):
            for i in range(len(norm) - n + 1):
                sub = norm[i : i + n]
                ngrams.append((f"c:{sub}", sub.strip()))

        counts: dict[str, int] = {}
        ngram_raw_map: dict[str, str] = {}
        for key, raw_str in ngrams:
            counts[key] = counts.get(key, 0) + 1
            if key not in ngram_raw_map:
                ngram_raw_map[key] = raw_str

        sparse_vec: dict[int, float] = {}
        for key, count in counts.items():
            idx = vocab.get(key)
            if idx is not None:
                tf = 1.0 + math.log(count)
                sparse_vec[idx] = tf * idfs[idx]

        norm_val = math.sqrt(sum(v * v for v in sparse_vec.values()))
        if norm_val > 0:
            for idx in sparse_vec:
                sparse_vec[idx] /= norm_val

        # 2. Compute logits and softmax probabilities
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
        trained_scores = {cls: math.exp(logits[cls] - max_logit) / exp_sum for cls in classes}

        # Report strictly the labels the model was trained on
        label_scores = {cls: round(prob, 4) for cls, prob in trained_scores.items()}
        tot = sum(label_scores.values())
        if tot > 0:
            label_scores = {k: round(v / tot, 4) for k, v in label_scores.items()}

        safe_prob = label_scores.get("safe", 0.5)
        risk = round(1.0 - safe_prob, 4)
        pred_label = max(label_scores, key=label_scores.get)  # type: ignore[arg-type]

        # 3. Explainability: Top contributing n-gram spans
        evidence: list[Evidence] = []
        target_cls = pred_label if pred_label != "safe" else "spam"
        w_target = weights.get(target_cls, [])

        candidate_spans: list[tuple[float, str, int, int]] = []
        if w_target:
            for key, idx in vocab.items():
                if idx in sparse_vec:
                    score = w_target[idx] * sparse_vec[idx]
                    if score > 0.05:
                        raw_sub = ngram_raw_map.get(key, "").strip()
                        if raw_sub and len(raw_sub) >= 3:
                            # Locate spans in original text
                            pattern = re.escape(raw_sub)
                            for match in re.finditer(pattern, text, re.IGNORECASE):
                                candidate_spans.append((score, raw_sub, match.start(), match.end()))

        # Deduplicate and sort spans by contribution
        candidate_spans.sort(key=lambda x: x[0], reverse=True)
        seen_spans: set[tuple[int, int]] = set()
        for score, term, start, end in candidate_spans[:4]:
            if (start, end) not in seen_spans:
                seen_spans.add((start, end))
                evidence.append(
                    Evidence(
                        kind="span",
                        description=f"Predictive pattern for {target_cls}",
                        payload={
                            "start": start,
                            "end": end,
                            "term": term,
                            "weight": round(score, 3),
                        },
                    )
                )

        # 4. Integrate rule-based lexicon flags
        lexicon_hits = scan_lexicon(text)
        for hit in lexicon_hits[:3]:
            if (hit.start, hit.end) not in seen_spans:
                seen_spans.add((hit.start, hit.end))
                evidence.append(
                    Evidence(
                        kind="span",
                        description=hit.description,
                        payload={
                            "start": hit.start,
                            "end": hit.end,
                            "term": hit.term,
                            "weight": hit.weight,
                        },
                    )
                )
            if hit.weight >= 0.5:
                evidence.append(
                    Evidence(
                        kind="flag",
                        description=hit.description,
                        payload={"category": hit.category, "term": hit.term, "weight": hit.weight},
                    )
                )

        latency_ms = max(1, int((time.perf_counter() - t0) * 1000))
        return ProviderResult(
            provider_id=self.id,
            ok=True,
            label_scores=label_scores,
            risk=risk,
            evidence=evidence,
            latency_ms=latency_ms,
            model_version=version,
            coverage=list(classes),
            error=None,
            validated=False,
        )
