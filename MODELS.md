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
- **P3 (Own)**: Forensic features (Error Level Analysis, 2D FFT radially-averaged power spectrum, noise residual statistics, EXIF/quantization table analysis) + heuristic classification head.
  - *Reported Model Version*: `heuristic_v0`.
  - *Status*: Carries `validated=false` until validated on frozen benchmark.
- **P2 (Open Source)**: Vision Transformer (ViT) image classification checkpoint fine-tuned for AI-generated vs. authentic image discrimination:
  - **ViT AI Image Detector** (`dima806/ai_vs_human_generated_image_detection`):
    - *License*: Apache License 2.0 (verified from Hugging Face model repository metadata and model card).
    - *Base Model*: `google/vit-base-patch16-224-in21k` (Apache 2.0).
    - *Training Data*: Curated dataset of human-created photographs vs. diffusion/GAN-synthesized AI images (Stable Diffusion, Midjourney, DALL-E).
    - *Architecture*: Vision Transformer (ViT) patch projection + self-attention encoder with classification head mapped to SKEPTID's `IMAGE_LABELS` (`authentic`, `filtered`, `ai_edited`, `ai_generated`).
    - *Lazy Loading & Fallback*: Loads model pipeline on-demand; cleanly falls back with `ok=False, error="optional_dependency_not_installed"` if dependencies or weights are unavailable.
    - *Reported Model Version*: `vit:dima806/ai_vs_human_generated_image_detection` with `validated=false`.
- **P1 (External)**: Server-side multi-vendor router (Gemini 3.8 Flash, Groq, OpenRouter, Cloudflare Workers AI) supporting multimodal vision inputs.

## Checkpoint Registry Status
See `models/registry.json` for active versions, holdout evaluations, confusion matrices, and gated promotion records.
