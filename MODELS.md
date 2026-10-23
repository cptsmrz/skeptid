# SKEPTID: Model Provenance and Registry

All official model evaluation metrics are written strictly by evaluation scripts into `models/registry.json`. No metrics are hardcoded.

## Model Classes and Architecture

### Text Engine

- **P3 (Own)**:
  - **Architecture**: Pure-Python TF-IDF vectorizer (word unigrams/bigrams and boundary-padded character 3-5 grams with sublinear term-frequency scaling and L2 normalization) coupled to a multinomial logistic regression classifier (`training/train_text.py`, exported to `models/text_v1.joblib`). Trained using Stochastic Gradient Descent (SGD) with inverse-frequency class weighting to handle label imbalance across the 5 text classes (`safe`, `phishing`, `spam`, `threat`, `bullying`).
  - **Calibration (Honest Description)**: Probabilities are direct softmax outputs computed over raw linear model logits ($z_c = b_c + \sum w_{cj} x_j$) normalized across classes. There is **no post-hoc calibration** (e.g. no temperature scaling, Platt scaling, or isotonic regression applied). Confidence scores represent raw discriminant margins mapped through softmax rather than calibrated Bayesian posterior probabilities.
  - **Explainability**: Top positive n-gram coefficients contributing to the predicted non-safe class are mapped directly back to character offsets in the input text (`Evidence(kind="span")`), supplemented by regex rule-based flags from `forensics/lexicon.py` (urgency, credential harvest, threats, and abusive terms).

- **P2 (Open Source)**:
  Composite pipeline loaded on-demand via Hugging Face `transformers` with graceful fallback (`ok=False, error="optional_dependency_not_installed"`):
  1. **Detoxify / Toxic-BERT**:
     - **Exact Checkpoint**: `unitary/toxic-bert` (loaded via `transformers.pipeline("text-classification", model="unitary/toxic-bert", top_k=None)` or fallback `Detoxify("original")`).
     - **Architecture**: `bert-base-cased` fine-tuned for multi-label toxic comment classification.
     - **Licence**: Apache License 2.0.
     - **Training Data**: Kaggle Jigsaw Toxic Comment Classification Challenge (Wikipedia talk page comments annotated for toxicity, severe toxicity, obscene, threat, insult, identity attack).
     - **Label Mapping**: `threat` maps directly to `threat`; `bullying` is derived as `max(insult, severe_toxicity, toxicity)`.
  2. **OpenTextShield**:
     - **Exact Checkpoint**: `telecomsxchange/OpenTextShield` (loaded via `transformers.pipeline("text-classification", model="telecomsxchange/OpenTextShield", top_k=None)`).
     - **Architecture**: `distilbert-base-uncased` fine-tuned for SMS and email fraud detection.
     - **Licence**: MIT License.
     - **Training Data**: Aggregated public SMS and email corpuses (including SMS Spam Collection, Enron spam/ham datasets, and curated phishing email corpora).
     - **Label Mapping**: Phishing signals map to `phishing`, spam signals map to `spam`, and ham/legit signals map to `safe`. Residual safe probability is computed as $1 - \max(\text{threats})$, with renormalization across all 5 classes.
  - *Reported Model Version*: `detoxify_textshield_v1`.

- **P1 (External)**:
  Server-side multi-vendor router (Gemini 3.8 Flash, Groq, OpenRouter, Cloudflare Workers AI) with structured JSON schemas and vendor failover.

---

### Image Engine

- **P3 (Own)**:
  Forensic extraction suite (`forensics/*`) implemented in NumPy and Pillow: Error Level Analysis (ELA), 2D FFT radially averaged power spectrum (high-frequency energy ratio), noise residual statistics (variance, kurtosis, cross-channel covariance), and EXIF / quantization table analysis.
  - *Head*: Heuristic forensic classification head producing anomaly maps (`Evidence(kind="heatmap")`) labeled as "forensic anomaly map" (not model attention).
  - *Reported Model Version*: `heuristic_v0`.
  - *Status*: Carries `validated=false` until benchmarked against frozen image holdouts.

- **P2 (Open Source)**:
  Vision Transformer (ViT) checkpoint for AI-generated vs. authentic image discrimination:
  - **Exact Checkpoint**: `dima806/ai_vs_human_generated_image_detection` (loaded via `transformers.pipeline("image-classification", model="dima806/ai_vs_human_generated_image_detection", top_k=None)`).
  - **Licence**: Apache License 2.0.
  - **Base Model**: `google/vit-base-patch16-224-in21k` (Vision Transformer, Apache 2.0).
  - **Training Data**: Curated dataset of ~96,000 images comprising human-captured photographs vs. AI diffusion and GAN generated images (Stable Diffusion, Midjourney, DALL-E).
  - **Binary Coverage**: `coverage = ["authentic", "ai_generated"]`. The underlying checkpoint is strictly a binary classifier (AI-generated vs. human). The previous four-label claim has been removed: while a schema-compatible heuristic projection across `IMAGE_LABELS` is computed in `label_scores`, the true validated coverage is strictly binary (`["authentic", "ai_generated"]`), which per SPEC section 5 excludes it from the primary promotion gate without full-modality coverage.
  - *Reported Model Version*: `vit:dima806/ai_vs_human_generated_image_detection` with `validated=false`.

- **P1 (External)**:
  Server-side multi-vendor router supporting multimodal image payloads across external vision models.

---

## Checkpoint Registry Status
See `models/registry.json` for active versions, holdout evaluations, confusion matrices, and gated promotion records.
