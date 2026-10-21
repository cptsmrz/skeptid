# SKEPTID: Build Specification

Multi-modal content-trust platform. Input: email/text, image, video (audio optional). Output: verdict + risk + **evidence**.
Read this file fully before writing code. Follow the milestone order. Stop for approval after each milestone.

---

## 0. Rules for the implementing agent

1. **Offline-first.** Every provider has a `mock` mode. The full app must run and pass tests with no network and no API keys.
2. **No fabricated numbers.** Never hardcode metrics, accuracies, or sample verdicts into UI, README, or dashboard. All metrics come from `models/registry.json`, written by the evaluation script.
3. **No loops.** If the same fix fails twice, stop and report the error, what was tried, and a proposed alternative.
4. **Record provenance.** Every dataset and pretrained checkpoint goes into `DATA.md` / `MODELS.md` with name, source URL, licence, and how it is used. Verify licences. Substitute a dataset if one is unavailable and note it.
5. **No secrets in code, logs, responses, or git.** Keys come from environment variables only.
6. **Quality bar:** type hints, `ruff` clean, modules under ~300 lines, one responsibility per module, tests for every milestone.
7. **Honest framing.** Output is a *risk score with evidence, not proof*. Do not label anything "trained from scratch" if it uses a pretrained encoder.
8. Commit after each milestone with a clear message.

---

## 1. Goals and non-goals

**Goals**
- Text/email: phishing, spam, threat, cyberbullying (about 80-90% of focus).
- Images: authentic / filtered / AI-edited / AI-generated (about 10% via email attachments, plus standalone).
- Video: sampled frames through the image engine, aggregated, with a timeline.
- Explainability on every verdict.
- Three providers per engine with automatic fallback and metric-gated promotion.
- Feedback loop that retrains the text model.

**Non-goals**
- Training large models from scratch.
- Guaranteed deepfake detection. Generalisation across unseen generators is limited and must be stated in the UI.
- Audio beyond a registered stub (stretch goal only).

---

## 2. Architecture

```
Client (SPA)
   │  HTTPS
[1] Gateway (FastAPI): validation, size limits, rate limit, auth to providers (keys server-side only)
   │
[2] Orchestrator: dispatch by modality → run provider chain → collect results
   │      config-driven: primary, fallback order, timeouts, shadow mode
   ├─ Engine: Text    ─┐
   ├─ Engine: Email   ─┤  each engine = feature/evidence logic + 3 providers
   ├─ Engine: Image   ─┤
   ├─ Engine: Video   ─┘  (frames → Image engine)
   │
[3] Providers (same interface for every engine)
   │   P1 external   : hidden API (server-side)
   │   P2 opensource : pretrained public checkpoint, unmodified
   │   P3 own        : SKEPTID forensic features + heads trained on public data
   │
[4] Fusion: combine signals into one risk score and level
   │
[5] Verdict + evidence (highlighted spans, heatmap, frame timeline)
   │
[6] Store (SQLite): analyses, per-provider results, feedback
   │
[7] Training loop: retrain → evaluate on frozen holdout → registry → gated promotion
        └──────────── updates P3 and config primary ────────────┘
```

Design principle: the Orchestrator and Fusion never know which provider type answered. Swapping primaries is a config change.

---

## 3. Repository layout

```
skeptid/
├── SPEC.md  README.md  DATA.md  MODELS.md  LIMITS.md
├── pyproject.toml  .env.example  .gitignore  Makefile
├── config/skeptid.yaml
├── src/skeptid/
│   ├── main.py                    # FastAPI app factory
│   ├── api/        routes.py  schemas.py  security.py  validators.py
│   ├── core/       types.py  interfaces.py  orchestrator.py  fusion.py  config.py
│   ├── providers/  external.py  opensource.py  own_text.py  own_image.py  mock.py
│   ├── engines/    text.py  email.py  image.py  video.py  audio_stub.py
│   ├── forensics/  ela.py  spectrum.py  noise.py  exif.py  urls.py  headers.py  lexicon.py
│   ├── training/   prepare_text.py  train_text.py  train_image_head.py  evaluate.py  retrain.py  registry.py
│   └── store/      db.py  models.py
├── web/            index.html  app.js  styles.css      # served as static files by FastAPI
├── data/           (gitignored) raw/  processed/  holdout/
├── models/         registry.json  text_v1.joblib ...
├── notebooks/      image_head_colab.ipynb
└── tests/          unit/  integration/  e2e_smoke.py
```

---

## 4. Core contracts (`core/types.py`, `core/interfaces.py`)

```python
class Modality(str, Enum): TEXT="text"; EMAIL="email"; IMAGE="image"; VIDEO="video"; AUDIO="audio"

TEXT_LABELS  = ["safe","phishing","spam","threat","bullying"]
IMAGE_LABELS = ["authentic","filtered","ai_edited","ai_generated"]

@dataclass
class Evidence:
    kind: Literal["span","heatmap","frame_score","metric","flag"]
    description: str
    payload: dict            # span: {start,end,weight}; heatmap: {png_b64}; frame_score: {t,score}

@dataclass
class ProviderResult:
    provider_id: str                 # "external" | "opensource" | "own"
    ok: bool
    label_scores: dict[str,float]    # calibrated probabilities over the modality's labels
    risk: float                      # 0..1 = 1 - P(safe/authentic)
    evidence: list[Evidence]
    latency_ms: int
    model_version: str
    error: str | None = None

class Provider(Protocol):
    id: str
    modality: Modality
    async def analyze(self, payload: "AnalysisInput") -> ProviderResult: ...
    async def health(self) -> bool: ...
```

Rules: providers never raise to the orchestrator; they return `ok=False` with `error`. Timeouts enforced by the orchestrator, not the provider.

---

## 5. Orchestrator (`core/orchestrator.py`)

Config (`config/skeptid.yaml`):

```yaml
text:  { primary: own,      chain: [own, opensource, external],  shadow: true, timeout_s: 8 }
email: { primary: own,      chain: [own, opensource, external],  shadow: true, timeout_s: 8 }
image: { primary: external, chain: [external, opensource, own],  shadow: true, timeout_s: 12 }
video: { primary: external, chain: [external, opensource, own],  shadow: true, timeout_s: 12, top_k_to_external: 4 }
mode:  mock        # mock | live ; mock is the default for dev and tests
```

Behaviour:
1. Run all configured providers **concurrently** (`asyncio.gather` with per-provider timeout).
2. The **displayed result** comes from the first provider in `chain` that returned `ok=True` (normally the primary). The others are shadow results: stored, and shown in the "Providers" panel.
3. **Disagreement:** if `max(risk) - min(risk) > 0.40` across ok providers, set `disagreement=true` and reduce confidence (see Fusion).
4. If all providers fail, return HTTP 503 with a clear message. Never return a fabricated verdict.
5. Providers that fail 3 times in 60s are circuit-broken for 60s and skipped.

**Promotion gate** (`training/registry.py`): a modality's primary changes to `own` only if the candidate model's metrics in `registry.json` meet the gate, evaluated on the frozen holdout:
- Text: macro-F1 ≥ 0.90 and per-class recall ≥ 0.80.
- Image: `own` is never auto-promoted. It is fallback and cross-check unless an out-of-distribution (unseen generator) AUC ≥ 0.90 is recorded. Report both in-distribution and out-of-distribution numbers.

Promotion is a CLI command (`python -m skeptid.training.registry promote --modality text`) that rewrites the config. It must refuse if the gate is not met.

---

## 6. Engines and providers

### 6.1 Text engine
- Input: raw text, max 20,000 chars, normalised (unicode NFKC, whitespace).
- **P3 own:** TF-IDF (word 1-2 grams + char 3-5 grams) → Logistic Regression / calibrated LinearSVC, 5 classes. Class-weight balanced.
- **Explainability:** top contributing n-grams from model coefficients, mapped to character spans → `Evidence(kind="span")`. Also rule-based flags from `forensics/lexicon.py` (urgency, credential requests, threats, abusive terms).
- **P2 opensource:** pretrained text classifier checkpoint from Hugging Face (e.g. a spam/phishing or toxicity model with a permissive licence). Map its labels onto `TEXT_LABELS`; document the mapping in `MODELS.md`.
- **P1 external:** adapter for the hidden API (see 6.5).
- Stretch (only after M4): fine-tune a small transformer in Colab and register as `own` v2.

### 6.2 Email engine
- Accept raw text or `.eml`. Parse with stdlib `email`.
- Signals:
  - **Body text** → Text engine.
  - **URLs** (`forensics/urls.py`): IP-literal hosts, punycode/homoglyphs, shorteners, excessive subdomains, display-text vs href mismatch, suspicious TLDs.
  - **Headers** (`forensics/headers.py`): From vs Reply-To vs Return-Path mismatch, SPF/DKIM/DMARC results if present in `Authentication-Results`, missing/odd Message-ID.
  - **Image attachments** (first 3, max 10 MB each) → Image engine.
- Output: component scores + fused email risk with per-component evidence.

### 6.3 Image engine
- Validation: magic-byte check (JPEG/PNG/WebP), max 10 MB, max 8192 px side, Pillow decompression-bomb guard.
- **P3 own** (`forensics/*`, written by us with NumPy and Pillow):
  - ELA: re-save at fixed JPEG quality, difference map, block statistics.
  - Frequency: 2D FFT, radially averaged power spectrum, high-frequency energy ratio.
  - Noise residual: high-pass filter residual statistics (mean, variance, kurtosis) per channel.
  - Metadata: EXIF presence, software tag, dimensions anomalies, quantisation tables.
  - Optional embedding from a pretrained encoder behind a flag (`use_encoder: true`). If used, it must be disclosed in `MODELS.md` and the README.
  - Classifier head: gradient boosting or logistic regression over the features, 4 classes (`IMAGE_LABELS`). Trained with `train_image_head.py`, runnable in Colab.
- **Heatmap:** block-level anomaly map from ELA and noise residual, rendered as a PNG overlay. Label it in the UI as **"forensic anomaly map"**, not model attention.
- **P2 opensource:** pretrained image-classification detector from Hugging Face; record name and licence.
- **P1 external:** adapter for the hidden API.

### 6.4 Video engine
- Validation: container check, max 50 MB, max 60 s, magic bytes.
- Sample `N=16` frames uniformly with OpenCV (configurable). Each frame goes through the Image engine. To control API cost, only the `top_k_to_external` frames ranked by `own` risk are sent to P1.
- Aggregate: mean, max, top-k mean, and temporal variance of risk. Video risk = 0.5·top-k mean + 0.3·max + 0.2·mean, configurable.
- Evidence: `frame_score` list (timestamp, score) for the timeline, plus the heatmap of the highest-risk frame.
- Temporal-consistency flag: high variance between adjacent frames raises a `flag` evidence item.

### 6.5 External provider (hidden API)
- `providers/external.py` has one adapter class per modality with `base_url`, `api_key` from env (`EXTERNAL_API_URL`, `EXTERNAL_API_KEY`).
- The exact vendor is configured by the owner. Implement the adapter against a small internal request/response shape, and isolate vendor specifics in one function (`_to_vendor_request` / `_from_vendor_response`) so the vendor can be swapped without touching anything else.
- In `mock` mode it returns deterministic synthetic results (seeded by the input hash) and is clearly tagged `model_version="mock"`. The UI must show a visible **MOCK** badge whenever any mock provider answered.
- Retries: 1 retry on 5xx with jitter; no retry on 4xx. Never log request bodies or keys.

### 6.6 Audio
- Register `audio_stub.py` implementing the `Provider` interface and returning `ok=False, error="not_implemented"`. UI shows the Audio tab disabled with "coming soon". No further work unless all milestones are complete.

---

## 7. Fusion (`core/fusion.py`)

Pure functions, fully unit-tested.

- **Single-modality verdict:** `risk` from the displayed provider.
- **Email:** `risk = 0.60·text + 0.15·url + 0.15·header + 0.10·attachment`, weights renormalised when a component is absent. Floor rule: if any component ≥ 0.90, final risk ≥ 0.80.
- **Level:** LOW < 0.35 ≤ MEDIUM < 0.70 ≤ HIGH. Thresholds in config.
- **Confidence:** `confidence = 1 - normalised_entropy(label_scores)`, multiplied by 0.7 if `disagreement`, and by 0.8 if only one provider returned ok.
- Weights and thresholds are heuristics. Document that in `LIMITS.md` and tune on the validation split only.

---

## 8. API (`api/routes.py`)

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/api/analyze/text` | `{text}` | |
| POST | `/api/analyze/email` | multipart: `eml` file or `raw` text | |
| POST | `/api/analyze/image` | multipart: `file` | |
| POST | `/api/analyze/video` | multipart: `file` | |
| POST | `/api/feedback` | `{analysis_id, correct: bool, true_label?}` | |
| GET | `/api/metrics` | | from `registry.json` and DB aggregates |
| GET | `/api/providers/status` | | names and up/down only, never URLs or keys |
| GET | `/healthz` | | |

Verdict response:

```json
{
  "id": "uuid", "modality": "email", "label": "phishing",
  "risk": 0.87, "level": "HIGH", "confidence": 0.74,
  "disagreement": false, "primary_provider": "own", "mock": false,
  "providers": [{"id":"own","ok":true,"risk":0.87,"model_version":"text_v1","latency_ms":41}, ...],
  "evidence": [{"kind":"span","description":"Urgency + credential request","payload":{"start":12,"end":48,"weight":0.31}}],
  "limits_note": "Risk score with evidence, not proof."
}
```

---

## 9. Security and privacy (`api/security.py`, `validators.py`)

- API keys only from env; `.env` gitignored; `.env.example` committed with empty values.
- Rate limit: 30 requests/min/IP (token bucket); stricter on video (5/min).
- Validate by magic bytes, not extension. Enforce size, duration, and char limits before any processing.
- Uploaded media processed in temp files, deleted in `finally`. Not persisted unless the user opts in via feedback. Store only the hash, label, scores, and (for text) the text the user explicitly submits as feedback.
- CORS locked to the app's own origin. Security headers set (CSP, X-Content-Type-Options, X-Frame-Options).
- `/api/providers/status` exposes nothing sensitive. Error messages never include upstream responses.
- Feedback endpoint: dedupe by hash, rate-limited, labelled `source=demo` and excluded from the frozen holdout.

---

## 10. Data and training

| Modality | Public datasets (verify licence/terms) |
|---|---|
| Text spam | SMS Spam Collection (UCI) |
| Text phishing | Nazario phishing corpus; Enron corpus (as legitimate email) |
| Threat / bullying | Jigsaw Toxic Comment (threat/toxic labels); a public cyberbullying tweets dataset |
| Image | CIFAKE; 140k Real and Fake Faces |
| Video | FaceForensics++ (access request required; use only if granted by the time of M5) |
| Audio (stretch) | ASVspoof |

Pipeline:
1. `prepare_text.py` maps every source onto `TEXT_LABELS`, records `source` per row, dedupes, and creates **train / val / frozen holdout** splits (70/15/15, stratified, fixed seed). Holdout is written once and never regenerated or mixed with feedback data.
2. `train_text.py` trains the baseline and saves `models/text_vN.joblib`.
3. `evaluate.py` computes accuracy, macro-F1, per-class precision/recall, confusion matrix, and (image) AUC in-distribution and out-of-distribution, then writes `models/registry.json`.
4. `retrain.py`: merges base training data with reviewed feedback labels (min 20 new labels, deduped), trains a candidate, evaluates on the frozen holdout, and promotes only if it does not regress. Triggered by CLI or the dashboard button.

Colab notebook (`notebooks/image_head_colab.ipynb`): installs deps, mounts Drive, loads the dataset, extracts features with the same `forensics` package (imported from the repo), trains the head, evaluates, and exports `models/image_head_vN.joblib`. Runs on a free T4 GPU.

---

## 11. UI (`web/`)

Single-page app served by FastAPI. Plain HTML/CSS/JS, no build step. Responsive and keyboard accessible.

- Tabs: Text · Email · Image · Video · Audio (disabled) · Dashboard.
- **Verdict card:** label, risk gauge, level colour, confidence, limits note, MOCK badge when applicable.
- **Providers panel:** the three providers' risks side by side, agreement/disagreement indicator, latency, model version.
- **Evidence view:** highlighted spans in text, URL/header flag list for email, heatmap overlay with opacity slider for images, risk-over-time chart for video with clickable frames.
- **Feedback:** "Correct" / "Wrong, it was…" buttons.
- **Dashboard:** active primary per modality, metrics per model version from the registry, confusion matrix, provider agreement rate, fallback count, p50/p95 latency, retrain button.
- "Try an example" buttons using bundled harmless samples.
- Clear, professional design. Dark and light theme. No external CDN dependencies required.

---

## 11b. Testing

- **Unit:** types, validators, fusion math, forensic features (deterministic on fixed inputs), URL/header parsers, registry gate refusal.
- **Orchestrator:** fake providers for success, error, timeout, and disagreement. Verify the fallback order, circuit breaker, and the 503 path.
- **Integration:** FastAPI `TestClient` against mock providers for all analyze endpoints and feedback.
- **E2E smoke:** `tests/e2e_smoke.py` starts the app in mock mode and exercises every endpoint.
- Target: all tests green before each milestone closes. `make test` runs everything.

---

## 12. Milestones (stop for approval after each)

| # | Deliverable | Acceptance |
|---|---|---|
| **M1** | Scaffold, `core/` contracts, config, mock providers, orchestrator with fallback, FastAPI skeleton, `/healthz`, tests | `make test` green; mock text analysis works end to end via API |
| **M2** | Text pipeline: `prepare_text`, `train_text`, `evaluate`, `own_text` provider with span evidence, registry, gate | Trained model loads; holdout metrics written by the script; promotion refuses when the gate is unmet |
| **M3** | Image engine: forensics, `own_image` heuristic baseline, heatmap, validators, P2 and P1 adapters (mock-capable) | Image endpoint returns verdict plus heatmap; forensic unit tests pass |
| **M4** | Email engine, fusion, feedback store, shadow-mode logging | `.eml` with a phishing sample returns fused verdict with URL, header, and text evidence |
| **M5** | Web UI complete, dashboard, video engine, retrain loop | All tabs work in mock mode; video timeline renders; retrain produces a candidate and applies the gate |
| **M6** | Colab image-head training, hardening, README, LIMITS, DATA, MODELS, deployment config (Hugging Face Space or Render), live-mode config for the hidden API | Deployed demo reachable; README has run, test, and deploy steps and an honest limits section |
| **Stretch** | Audio provider, fine-tuned transformer as `own` v2 | Only after M6 is complete |

Suggested time budget (24h): M1 2h · M2 3h · M3 3h · M4 2h · M5 4h · M6 4h · buffer 6h.

---

## 13. Definition of done

- App runs with `make run` in mock mode and in live mode with env keys.
- All tests green. No secrets in the repo.
- Every number shown in the UI traces back to `registry.json` or the database.
- README includes architecture diagram, setup, data provenance, the three-provider design, and a **Limitations** section that states: risk score not proof, weak generalisation to unseen generators and heavy compression, heuristic fusion weights, and which components use pretrained models.