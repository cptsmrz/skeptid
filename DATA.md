# SKEPTID: Data Provenance

This document records the provenance, licenses, and usage of all datasets utilized in the SKEPTID platform.

## Planned Datasets

## Text Modality Datasets

### Text Spam (Automated Download)
- **Dataset**: SMS Spam Collection
- **Source**: UCI Machine Learning Repository (`https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip`)
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Target Path**: `data/raw/sms_spam_collection/SMSSpamCollection`
- **Automation**: Downloaded automatically by `python -m skeptid.training.prepare_text` (no login required).
- **Labels**: `ham` -> `safe`, `spam` -> `spam`.

### Text Phishing
- **Dataset**: Phishing Emails & Texts Dataset
- **Source**: Hugging Face (`ealvaradob/phishing-dataset` -> `texts.json`)
- **License**: Apache License 2.0 (verified from HF repository metadata)
- **Target Path**: `data/raw/nazario_phishing.csv`
- **Automation**: Public Hugging Face dataset auto-downloaded by `prepare_text.py` without login credentials.
- **Expected Columns**: `text`, `label`
- **Labels**: `label == 1` -> `phishing` (over 7,600 samples), `label == 0` -> `safe` (over 12,000 samples).
- **Alternative / Legacy**: Nazario Phishing Corpus (`~jose/phishing`) & CMU Enron Corpus (`enron_clean.csv`).

### Cyberbullying
- **Dataset**: Cyberbullying Dataset
- **Source**: Hugging Face (`AnikaBasu/CyberbullyingDataset` -> `ParsedAnikaBCyberbullyingDataset.json`)
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Target Path**: `data/raw/cyberbullying_tweets.csv`
- **Automation**: Public Hugging Face dataset auto-downloaded by `prepare_text.py` without login credentials.
- **Expected Columns**: `tweet_text`, `cyberbullying_type` (or `instruction`, `output`)
- **Labels**: `gender`, `religion`, `other_cyberbullying`, `age`, `ethnicity` -> `bullying` (over 2,500 samples), `not_cyberbullying` -> `safe`.

### Threat & Toxicity
- **Dataset**: Jigsaw Toxic Comment Classification Challenge (Mirror)
- **Source**: Hugging Face (`thesofakillers/jigsaw-toxic-comment-classification-challenge` -> `train.csv` and `google/jigsaw_toxicity_pred`)
- **License**: CC-BY-SA-3.0 / CC0 1.0 (verified from HF repository metadata)
- **Target Path**: `data/raw/jigsaw_toxic.csv`
- **Automation**: Public Hugging Face dataset auto-downloaded by `prepare_text.py` without login credentials.
- **Expected Columns**: `comment_text`, `threat`, `toxic`, `severe_toxic`, `insult`
- **Labels**: rows with `threat == 1` -> `threat` (over 470 samples); rows with `toxic == 1` or `insult == 1` or `severe_toxic == 1` -> `bullying`.
- **Note on Kaggle Token**: While Kaggle requires `kaggle.json` credentials for direct API downloads, public Hugging Face mirrors allow automated no-login downloading.

> **Class Coverage Status**: All 5 `TEXT_LABELS` (`safe`, `phishing`, `spam`, `threat`, `bullying`) are fully populated and integrated into `data/holdout/text_holdout_v1.csv` and `data/processed/text_train.csv`. Zero missing classes.

### Image
- **Dataset**: CIFAKE: Real and AI-Generated Synthetic Images
- **Source**: Kaggle / Research
- **License**: CC BY-SA 4.0
- **Usage**: Real vs synthetic image forensic feature evaluation.
- **Dataset**: 140k Real and Fake Faces
- **Source**: Kaggle / NVIDIA Flickr-Faces-HQ (FFHQ) & StyleGAN
- **License**: CC BY-NC 4.0 / Research
- **Usage**: Evaluation of face artifacts and synthetic noise profiles.

### Video
- **Dataset**: FaceForensics++ (subject to access request)
- **Source**: Technical University of Munich
- **License**: Non-commercial research agreement
- **Usage**: Uniform frame temporal sampling evaluation.

### Feedback Data
- **Source**: User feedback endpoint (`/api/feedback`)
- **Status**: Kept in local SQLite database, deduped by hash, tagged `source=demo`, and strictly excluded from the frozen holdout split.
