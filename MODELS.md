# SKEPTID: Model Provenance and Registry

All official model evaluation metrics are written strictly by evaluation scripts into `models/registry.json`. No metrics are hardcoded.

## Model Classes and Architecture

### Text Engine
- **P3 (Own)**: TF-IDF (word 1-2 grams + char 3-5 grams) with Logistic Regression / calibrated LinearSVC across 5 classes (`safe`, `phishing`, `spam`, `threat`, `bullying`). Class-weight balanced. Explainability via top coefficient n-gram character spans mapped to input offsets, augmented by rule flags from `forensics/lexicon.py`.
- **P2 (Open Source)**: Composite open-source pipeline (lazy-loaded, optional dependencies, clean fallback):
  - **Detoxify** (`unitaryai/detoxify` v0.5.4 / `unitary/toxic-bert`): Evaluates toxicity, threat, and insult labels, mapped to `threat` and `bullying`.
    - *License*: Apache License 2.0 (verified from `.venv/Lib/site-packages/detoxify-0.5.4.dist-info/licenses/LICENSE` and Hugging Face card metadata).
    - *Model Checkpoint*: `unitary/toxic-bert` (BERT-base-cased fine-tuned on Jigsaw Toxic Comment Classification Challenge).
  - **OpenTextShield** (`telecomsxchange/OpenTextShield`): SMS & email spam/phishing classification checkpoint (labels: `ham`, `spam`, `phishing`).
    - *License*: MIT License (verified from Hugging Face model repository metadata).
    - *Model Checkpoint*: `telecomsxchange/OpenTextShield` (DistilBERT-based binary/multi-class text shield).
  - *Reported Model Version*: `detoxify_textshield_v1`.
  - If optional libraries or checkpoints are uninstalled, provider cleanly falls back reporting `ok=False, error="optional_dependency_not_installed"`.
- **P1 (External)**: Server-side hidden API adapter.

### Image Engine
- **P3 (Own)**: Forensic features (Error Level Analysis, 2D FFT radially-averaged power spectrum, noise residual statistics, EXIF/quantization table analysis) + classification head.
- **P2 (Open Source)**: Pretrained image detector checkpoint from Hugging Face.
- **P1 (External)**: Server-side hidden API adapter.

## Checkpoint Registry Status
See `models/registry.json` for active versions, holdout evaluations, confusion matrices, and gated promotion records.
