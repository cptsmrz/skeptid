# SKEPTID: Data Provenance

This document records the provenance, licenses, and usage of all datasets utilized in the SKEPTID platform.

## Planned Datasets

### Text Spam
- **Dataset**: SMS Spam Collection
- **Source**: UCI Machine Learning Repository
- **License**: Creative Commons Attribution 4.0 International (CC BY 4.0)
- **Usage**: Training baseline text classifier on spam vs legitimate messages.

### Text Phishing
- **Dataset**: Nazario Phishing Corpus
- **Source**: Monkey.org (~jose/phishing)
- **License**: Public / Research use
- **Usage**: Phishing email body extraction and training.
- **Dataset**: Enron Email Dataset
- **Source**: CMU Enron Corpus
- **License**: Public domain / research release
- **Usage**: Legitimate email body and header baseline.

### Threat and Bullying
- **Dataset**: Jigsaw Toxic Comment Classification Challenge
- **Source**: Kaggle / Jigsaw
- **License**: CC0 Public Domain
- **Usage**: Toxic, threat, and severe toxic label extraction.
- **Dataset**: Cyberbullying Classification Dataset
- **Source**: Kaggle / Public research
- **License**: Open Data Commons Public Domain Dedication and License (PDDL) / CC BY 4.0
- **Usage**: Social media cyberbullying text classification.

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
