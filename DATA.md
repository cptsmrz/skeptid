# SKEPTID: Data Provenance

All numbers in this file are counts from the actual raw CSV files on disk, not estimates.
All licences were verified from the Hugging Face model card or the UCI repository page.

---

## Text Modality Datasets

### SMS Spam Collection (→ `safe`, `spam`)
| Attribute | Value |
|-----------|-------|
| **File on disk** | `data/raw/sms_spam_collection/SMSSpamCollection` |
| **True source** | UCI Machine Learning Repository — "SMS Spam Collection" |
| **Source URL** | `https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip` |
| **Licence** | Creative Commons Attribution 4.0 International (CC BY 4.0) |
| **Download** | Automated by `prepare_text.py` — no login required |
| **Raw labels** | `ham` → `safe`, `spam` → `spam` |
| **Class counts** | `safe`: 4,516 · `spam`: 642 (raw file) |

> ⚠️ **Single-source classes:** `spam` comes exclusively from this dataset.

---

### HF Phishing Dataset (→ `phishing`, `safe`)
| Attribute | Value |
|-----------|-------|
| **File on disk** | `data/raw/hf_phishing.csv` |
| **True source** | Hugging Face dataset `ealvaradob/phishing-dataset`, file `texts.json` |
| **Original source** | Compiled corpus of verified phishing emails/URLs and legitimate emails (Enron, Linguist List) |
| **Source URL** | `https://huggingface.co/datasets/ealvaradob/phishing-dataset` |
| **Licence** | Apache License 2.0 (verified from HF repository card) |
| **Download** | Automated by `prepare_text.py` via `huggingface_hub.hf_hub_download` — no login required |
| **Rows ingested** | 4,000 (2,000 phishing rows `label == 1` + 2,000 matched safe rows `label == 0`) |
| **Raw labels** | `label == 1` → `phishing`, `label == 0` → `safe` |
| **Class counts** | `phishing`: 2,000 · `safe`: 2,000 (rows in raw file) |

> ⚠️ **Single-source class:** `phishing` comes exclusively from this dataset.

---

### Jigsaw Toxic Comment Classification (→ `threat`, `bullying`, `safe`)
| Attribute | Value |
|-----------|-------|
| **File on disk** | `data/raw/jigsaw_toxic.csv` |
| **True source** | Hugging Face dataset `thesofakillers/jigsaw-toxic-comment-classification-challenge`, file `train.csv` |
| **Original source & terms** | Kaggle *Toxic Comment Classification Challenge* (2018) by Jigsaw and Google's Conversation AI. Built on Wikipedia Talk Page edits. Underlying Wikipedia text is licensed under CC-BY-SA 3.0 and GFDL by the Wikimedia Foundation; dataset released on Kaggle under CC0 / CC-BY-SA 3.0 terms. |
| **Source URL** | `https://huggingface.co/datasets/thesofakillers/jigsaw-toxic-comment-classification-challenge` |
| **Licence** | CC0 1.0 / CC-BY-SA 3.0 (verified from HF repository card and Kaggle challenge terms) |
| **Download** | Automated by `prepare_text.py` via `huggingface_hub.hf_hub_download` — no login required |
| **Label mapping** | `threat == 1` → `threat`; `(toxic == 1 OR insult == 1 OR severe_toxic == 1) AND threat == 0` → `bullying`; all 6 toxicity flags == 0 → `safe` |
| **Class counts** | `threat`: 478 · `bullying`: 1,500 · `safe`: 1,500 (rows in file on disk) |

> ⚠️ **Single-source class:** `threat` comes exclusively from this dataset.

---

### Cyberbullying Dataset (→ `bullying`, `safe`)
| Attribute | Value |
|-----------|-------|
| **File on disk** | `data/raw/cyberbullying_tweets.csv` |
| **True source** | Hugging Face dataset `AnikaBasu/CyberbullyingDataset`, file `ParsedAnikaBCyberbullyingDataset.json` |
| **Source URL** | `https://huggingface.co/datasets/AnikaBasu/CyberbullyingDataset` |
| **Licence** | Creative Commons Attribution 4.0 International (CC BY 4.0) (verified from HF repository card) |
| **Download** | Automated by `prepare_text.py` via `huggingface_hub.hf_hub_download` — no login required |
| **Label mapping** | All rows where `output != "not_cyberbullying"` → `bullying`; rows where `output == "not_cyberbullying"` → `safe` |
| **Class counts** | `bullying`: 2,522 · `safe`: 434 (rows in file on disk) |

---

## Consolidated Class Counts (train split, 70% of deduplicated data, seed 42)

| Class | Train | Val | Holdout v2 | Source(s) |
|-------|-------|-----|------------|-----------|
| `safe` | 5,911 | 1,267 | 1,267 | sms_spam_uci + hf_phishing + jigsaw_toxic + hf_cyberbullying |
| `bullying` | 2,815 | 603 | 603 | hf_cyberbullying + jigsaw_toxic |
| `phishing` | 1,398 | 300 | 300 | hf_phishing (ealvaradob) only |
| `spam` | 450 | 96 | 96 | sms_spam_uci only |
| `threat` | 334 | 72 | 72 | jigsaw_toxic only |
| **Total** | **10,908** | **2,338** | **2,338** | Deduplicated total: 15,584 |

> **Holdout v2 (2,338 rows):** SHA-256 `d28f874bf7fead718ef3d0ffd9cb7812ebf47edab7e992ae0b5fbd344f728b1c`, seed 42.
>
> *(Archived) Holdout v1 (1,748 rows):* SHA-256 `e626d9012e68f6ba9f7b4f11772f86257dc19c26d0787f2b625071328406b26a`, seed 42.

---

## Datasets Not Ingested (Manual Download Required)

| Dataset | Reason not ingested | Target path if provided |
|---------|---------------------|------------------------|
| Nazario Phishing Corpus (`~jose/phishing`) | Requires manual request to corpus owner | `data/raw/nazario_phishing_real.csv` (`text`, `label` columns) |
| Enron Email Corpus | Requires manual download (large archive) | `data/raw/enron_clean.csv` (`text`, `label=safe` columns) |

---

## Image Datasets (Planned — not yet ingested)

| Dataset | Source | Licence | Status |
|---------|--------|---------|--------|
| CIFAKE | Kaggle / Research | CC BY-SA 4.0 | Planned for M5 |
| 140k Real and Fake Faces | Kaggle / NVIDIA FFHQ + StyleGAN | CC BY-NC 4.0 / Research | Planned for M5 |

---

## Video Datasets (Planned)

| Dataset | Source | Licence | Status |
|---------|--------|---------|--------|
| FaceForensics++ | TU Munich | Non-commercial research agreement | Pending access grant |

---

## Feedback Data

- **Source:** User feedback endpoint (`/api/feedback`)
- **Status:** Stored in local SQLite, deduped by hash, tagged `source=demo`, strictly excluded from frozen holdout.
