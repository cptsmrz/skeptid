# SKEPTID: Model Provenance and Registry

All official model evaluation metrics are written strictly by evaluation scripts into `models/registry.json`. No metrics are hardcoded.

## Model Classes and Architecture

### Text Engine
- **P3 (Own)**: TF-IDF (word 1-2 grams + char 3-5 grams) with Logistic Regression / calibrated LinearSVC across 5 classes (`safe`, `phishing`, `spam`, `threat`, `bullying`). Class-weight balanced. Explainability via top coefficient n-gram character spans.
- **P2 (Open Source)**: Pretrained public checkpoint from Hugging Face (e.g. text toxicity / spam classifier). Documented label mappings to `TEXT_LABELS`.
- **P1 (External)**: Server-side hidden API adapter.

### Image Engine
- **P3 (Own)**: Forensic features (Error Level Analysis, 2D FFT radially-averaged power spectrum, noise residual statistics, EXIF/quantization table analysis) + classification head.
- **P2 (Open Source)**: Pretrained image detector checkpoint from Hugging Face.
- **P1 (External)**: Server-side hidden API adapter.

## Checkpoint Registry Status
See `models/registry.json` for active versions, holdout evaluations, confusion matrices, and gated promotion records.
