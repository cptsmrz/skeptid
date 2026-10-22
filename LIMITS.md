# SKEPTID: Limitations and Honest Framing

## Core Principles
1. **Risk Score, Not Proof**: SKEPTID produces calibrated risk scores with observable evidence indicators. It does not provide absolute proof of authenticity or malicious intent.
2. **Generalization Boundaries**:
   - Machine learning and heuristic forensic detectors are subject to evasion by novel generators, heavy recompression, or adversarial perturbations.
   - Out-of-distribution generators may exhibit features distinct from the training distribution.
3. **Fusion Heuristics**:
   - Multi-signal fusion weights (such as email text, URL, header, and attachment contributions) are rule-based heuristics calibrated on validation data.
   - Floor rules prioritize high-severity signals (e.g. verified malicious links or known threat triggers) but may yield elevated risk in benign anomaly cases.
4. **Pretrained Encoders**:
   - Any engine utilizing pretrained encoders or checkpoints is documented as utilizing transfer features and not labeled "trained from scratch".
5. **No Fabricated Certainty**:
   - When models or providers disagree (`max(risk) - min(risk) > 0.40`), disagreement is flagged and confidence is explicitly reduced.
   - If all providers fail, a 503 error is returned rather than generating a fallback verdict.

---

## Data Provenance Limits (Text Modality — holdout_v2)

With `holdout_v2`, matched negatives were introduced for `safe` across 4 distinct domains: SMS ham (`sms_spam_uci`), legitimate email (`hf_phishing` label 0), benign social posts (`hf_cyberbullying` not_cyberbullying), and civil forum comments (`jigsaw_toxic` benign). This resolved the failure on benign email structures, lifting 20-email probe accuracy from 45.0% to 85.0% (10/10 legitimate emails correctly recognized as safe).

However, the following classes still derive from a **single source only**:

| Class | Sole source | Risk |
|-------|-------------|------|
| `spam` | SMS Spam Collection (UCI) — short SMS messages only | May underperform on email spam, which is longer and formatted differently |
| `phishing` | `ealvaradob/phishing-dataset` (HF) | May not generalise to targeted spear-phishing emails with bespoke linguistic styles |
| `threat` | Jigsaw Toxic Comment Classification (HF mirror) — comment toxicity | Comments may differ from direct-message or email threats in tone and vocabulary |

`safe` draws from four sources and `bullying` draws from two sources (`jigsaw_toxic` + `hf_cyberbullying`).

---

## Image Model Limits

- `own_image` provider version `heuristic_v0`: **not validated on any labelled image dataset**.
  All scoring is based on handcrafted forensic heuristics (ELA, FFT, noise residual, EXIF inspection).
  No trained classifier head has been fitted; the provider is a forensic baseline only.
  Set `validated: false` in the registry. Do not promote as primary.
- No out-of-distribution AUC is available. `own` will not be auto-promoted for the image modality
  until an AUC ≥ 0.90 on an unseen-generator split is recorded.

