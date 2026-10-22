"""Dataset preparation pipeline for text modality.

Downloads public automated datasets (SMS Spam Collection), checks for optional
manual raw files, maps them to TEXT_LABELS, and generates train/val/frozen holdout splits (70/15/15).
Implemented purely with Python standard libraries for cross-platform resilience.
"""

import csv
import io
import random
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from skeptid.core.types import TEXT_LABELS

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
HOLDOUT_DIR = Path("data/holdout")

SMS_SPAM_URL = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
SMS_SPAM_DIR = RAW_DIR / "sms_spam_collection"
SMS_SPAM_FILE = SMS_SPAM_DIR / "SMSSpamCollection"


def download_public_hf_datasets(force: bool = False) -> None:
    """Download public Hugging Face datasets (no login required) with matched negatives."""
    jigsaw_path = RAW_DIR / "jigsaw_toxic.csv"
    phish_path = RAW_DIR / "hf_phishing.csv"
    cb_path = RAW_DIR / "cyberbullying_tweets.csv"

    if not force and jigsaw_path.exists() and phish_path.exists() and cb_path.exists():
        return

    try:
        import json

        import pandas as pd
        from huggingface_hub import hf_hub_download

        RAW_DIR.mkdir(parents=True, exist_ok=True)

        if force or not phish_path.exists():
            try:
                p_file = hf_hub_download(
                    "ealvaradob/phishing-dataset", "texts.json", repo_type="dataset"
                )
                with open(p_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                phish_rows = [
                    {"text": x["text"].strip(), "label": "phishing", "source": "hf_phishing"}
                    for x in data
                    if x.get("label") == 1 and x.get("text", "").strip()
                ][:2000]
                safe_rows = [
                    {"text": x["text"].strip(), "label": "safe", "source": "hf_phishing"}
                    for x in data
                    if x.get("label") == 0 and x.get("text", "").strip()
                ][:2000]
                combined_phish = phish_rows + safe_rows
                _write_csv(phish_path, combined_phish)
                print(f"[prepare_text] Auto-downloaded HF phishing dataset: {len(phish_rows)} phishing, {len(safe_rows)} safe matched rows")
            except (OSError, RuntimeError, ValueError, KeyError) as e:
                print(f"[prepare_text] Notice: could not auto-download HF phishing: {e}")

        if force or not cb_path.exists():
            try:
                cb_file = hf_hub_download(
                    "AnikaBasu/CyberbullyingDataset",
                    "ParsedAnikaBCyberbullyingDataset.json",
                    repo_type="dataset",
                )
                with open(cb_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cb_rows = [
                    {"text": x.get("instruction", "").strip(), "label": "bullying", "source": "hf_cyberbullying"}
                    for x in data
                    if x.get("output") != "not_cyberbullying" and x.get("instruction", "").strip()
                ]
                safe_cb_rows = [
                    {"text": x.get("instruction", "").strip(), "label": "safe", "source": "hf_cyberbullying"}
                    for x in data
                    if x.get("output") == "not_cyberbullying" and x.get("instruction", "").strip()
                ]
                combined_cb = cb_rows + safe_cb_rows
                _write_csv(cb_path, combined_cb)
                print(f"[prepare_text] Auto-downloaded HF cyberbullying dataset: {len(cb_rows)} bullying, {len(safe_cb_rows)} safe matched rows")
            except (OSError, RuntimeError, ValueError, KeyError) as e:
                print(f"[prepare_text] Notice: could not auto-download HF cyberbullying: {e}")

        if force or not jigsaw_path.exists():
            try:
                j_file = hf_hub_download(
                    "thesofakillers/jigsaw-toxic-comment-classification-challenge",
                    "train.csv",
                    repo_type="dataset",
                )
                df_j = pd.read_csv(j_file)
                threats = df_j[df_j["threat"] == 1]
                toxic = df_j[(df_j["threat"] == 0) & ((df_j["toxic"] == 1) | (df_j["insult"] == 1))].head(1500)
                benign = df_j[
                    (df_j["toxic"] == 0)
                    & (df_j["severe_toxic"] == 0)
                    & (df_j["obscene"] == 0)
                    & (df_j["threat"] == 0)
                    & (df_j["insult"] == 0)
                    & (df_j["identity_hate"] == 0)
                ].head(1500)

                j_rows: list[dict[str, str]] = []
                for _, r in threats.iterrows():
                    t = str(r.get("comment_text") or "").strip()
                    if t:
                        j_rows.append({"text": t, "label": "threat", "source": "jigsaw_toxic"})
                for _, r in toxic.iterrows():
                    t = str(r.get("comment_text") or "").strip()
                    if t:
                        j_rows.append({"text": t, "label": "bullying", "source": "jigsaw_toxic"})
                for _, r in benign.iterrows():
                    t = str(r.get("comment_text") or "").strip()
                    if t:
                        j_rows.append({"text": t, "label": "safe", "source": "jigsaw_toxic"})

                _write_csv(jigsaw_path, j_rows)
                print(f"[prepare_text] Auto-downloaded HF Jigsaw dataset: {len(threats)} threat, {len(toxic)} bullying, {len(benign)} safe matched rows")
            except (OSError, RuntimeError, ValueError, KeyError) as e:
                print(f"[prepare_text] Notice: could not auto-download HF Jigsaw: {e}")
    except ImportError:
        pass


def download_sms_spam() -> Path | None:
    """Download and extract SMS Spam Collection if not already present."""
    if SMS_SPAM_FILE.exists():
        return SMS_SPAM_FILE

    SMS_SPAM_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[prepare_text] Downloading SMS Spam Collection from {SMS_SPAM_URL}...")
    try:
        req = urllib.request.Request(
            SMS_SPAM_URL,
            headers={"User-Agent": "SKEPTID-ML-Pipeline/0.1"},
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            zip_bytes = response.read()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(SMS_SPAM_DIR)
        print(f"[prepare_text] Extracted SMS Spam Collection to {SMS_SPAM_DIR}")
        return SMS_SPAM_FILE
    except (urllib.error.URLError, OSError, zipfile.BadZipFile) as exc:
        print(f"[prepare_text] Warning: Could not download SMS Spam Collection: {exc}")
        return None


def load_sms_spam(path: Path) -> list[dict[str, str]]:
    """Parse SMS Spam Collection tab-separated file."""
    rows: list[dict[str, str]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            raw_lbl, text = row[0].strip().lower(), row[1].strip()
            if not text:
                continue
            if raw_lbl == "ham":
                mapped_lbl = "safe"
            elif raw_lbl == "spam":
                mapped_lbl = "spam"
            else:
                continue
            rows.append({"text": text, "label": mapped_lbl, "source": "sms_spam_uci"})
    return rows


def load_manual_datasets() -> list[dict[str, str]]:
    """Check for and load any optional manual raw datasets placed in data/raw/."""
    records: list[dict[str, str]] = []

    # 1. Jigsaw toxic
    jigsaw_path = RAW_DIR / "jigsaw_toxic.csv"
    if jigsaw_path.exists():
        print(f"[prepare_text] Found dataset: {jigsaw_path}")
        with open(jigsaw_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = (row.get("comment_text") or row.get("text") or "").strip()
                if not text:
                    continue
                if row.get("label"):
                    records.append({
                        "text": text,
                        "label": row["label"].strip(),
                        "source": (row.get("source") or "jigsaw_toxic").strip(),
                    })
                else:
                    threat_val = int(row.get("threat") or 0)
                    toxic_val = int(row.get("toxic") or 0)
                    insult_val = int(row.get("insult") or 0)
                    severe_val = int(row.get("severe_toxic") or 0)
                    obscene_val = int(row.get("obscene") or 0)
                    hate_val = int(row.get("identity_hate") or 0)

                    if threat_val == 1:
                        records.append({"text": text, "label": "threat", "source": "jigsaw_toxic"})
                    elif toxic_val == 1 or insult_val == 1 or severe_val == 1:
                        records.append({"text": text, "label": "bullying", "source": "jigsaw_toxic"})
                    elif (
                        threat_val == 0
                        and toxic_val == 0
                        and insult_val == 0
                        and severe_val == 0
                        and obscene_val == 0
                        and hate_val == 0
                    ):
                        records.append({"text": text, "label": "safe", "source": "jigsaw_toxic"})

    # 2. Phishing dataset (hf_phishing or legacy nazario_phishing)
    phish_path = RAW_DIR / "hf_phishing.csv"
    if not phish_path.exists():
        phish_path = RAW_DIR / "nazario_phishing.csv"
    if phish_path.exists():
        print(f"[prepare_text] Found dataset: {phish_path}")
        with open(phish_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = (row.get("text") or row.get("body") or "").strip()
                lbl = (row.get("label") or "phishing").strip()
                src = (row.get("source") or "hf_phishing").strip()
                if t:
                    records.append({"text": t, "label": lbl, "source": src})

    # 3. Enron clean
    enron_path = RAW_DIR / "enron_clean.csv"
    if enron_path.exists():
        print(f"[prepare_text] Found manual dataset: {enron_path}")
        with open(enron_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = (row.get("text") or row.get("body") or "").strip()
                if t:
                    records.append({"text": t, "label": "safe", "source": "enron_clean"})

    # 4. Cyberbullying tweets
    tweets_path = RAW_DIR / "cyberbullying_tweets.csv"
    if tweets_path.exists():
        print(f"[prepare_text] Found dataset: {tweets_path}")
        with open(tweets_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t = (row.get("tweet_text") or row.get("text") or "").strip()
                lbl = (row.get("label") or "bullying").strip()
                src = (row.get("source") or "hf_cyberbullying").strip()
                if t:
                    records.append({"text": t, "label": lbl, "source": src})

    return records


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Write list of dict rows to CSV file."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "source"])
        writer.writeheader()
        writer.writerows(rows)


def stratified_split(
    rows: list[dict[str, str]],
    seed: int = 42,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    """Perform a stratified 70% train / 15% val / 15% holdout split."""
    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_label[r["label"]].append(r)

    train_rows: list[dict[str, str]] = []
    val_rows: list[dict[str, str]] = []
    holdout_rows: list[dict[str, str]] = []

    rng = random.Random(seed)
    for _lbl, items in sorted(by_label.items()):
        shuffled = list(items)
        rng.shuffle(shuffled)
        n = len(shuffled)

        n_holdout = max(1, round(n * 0.15))
        n_val = max(1, round(n * 0.15))
        n_train = n - n_holdout - n_val

        if n_train <= 0:
            train_rows.extend(shuffled)
        else:
            train_rows.extend(shuffled[:n_train])
            val_rows.extend(shuffled[n_train:n_train + n_val])
            holdout_rows.extend(shuffled[n_train + n_val:])

    rng.shuffle(train_rows)
    rng.shuffle(val_rows)
    rng.shuffle(holdout_rows)
    return train_rows, val_rows, holdout_rows


def prepare_text_data(holdout_version: str = "v2", force_rebuild: bool = True) -> dict[str, int]:
    """Execute text dataset preparation, deduplication, and 70/15/15 splitting."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    HOLDOUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str]] = []

    # 1. Automated SMS spam download
    sms_file = download_sms_spam()
    if sms_file and sms_file.exists():
        sms_rows = load_sms_spam(sms_file)
        print(f"[prepare_text] Loaded {len(sms_rows)} rows from SMS Spam Collection.")
        all_rows.extend(sms_rows)

    # 2. Automated public HF datasets with matched negatives
    download_public_hf_datasets(force=force_rebuild)

    # 3. Manual / downloaded raw datasets
    manual_rows = load_manual_datasets()
    if manual_rows:
        print(f"[prepare_text] Loaded {len(manual_rows)} rows from raw datasets.")
        all_rows.extend(manual_rows)

    if not all_rows:
        raise RuntimeError("No text data available. Could not prepare text splits.")

    # 4. Deduplicate by text
    seen_texts: set[str] = set()
    deduped: list[dict[str, str]] = []
    for r in all_rows:
        t = r["text"]
        if t not in seen_texts:
            seen_texts.add(t)
            deduped.append(r)

    print(f"[prepare_text] Total deduplicated rows: {len(deduped)}")
    counts = Counter(r["label"] for r in deduped)
    for lbl, count in sorted(counts.items()):
        print(f"  {lbl}: {count}")

    # Check for missing classes
    present_labels = set(counts.keys())
    missing_labels = [lbl for lbl in TEXT_LABELS if lbl not in present_labels]
    if missing_labels:
        print(f"[prepare_text] Notice: Missing classes among TEXT_LABELS: {missing_labels}")
        print("[prepare_text] See DATA.md for instructions on placing raw data files to enable them.")

    # 5. Stratified splits: 70% train, 15% val, 15% holdout
    train_rows, val_rows, holdout_rows = stratified_split(deduped, seed=42)

    versioned_holdout = HOLDOUT_DIR / f"text_holdout_{holdout_version}.csv"
    active_holdout = HOLDOUT_DIR / "text_holdout.csv"
    train_file = PROCESSED_DIR / "text_train.csv"
    val_file = PROCESSED_DIR / "text_val.csv"

    _write_csv(versioned_holdout, holdout_rows)
    _write_csv(active_holdout, holdout_rows)
    print(f"[prepare_text] Wrote frozen holdout to {versioned_holdout} ({len(holdout_rows)} rows)")
    print(f"[prepare_text] Wrote active holdout to {active_holdout} ({len(holdout_rows)} rows)")

    _write_csv(train_file, train_rows)
    _write_csv(val_file, val_rows)
    print(f"[prepare_text] Wrote train to {train_file} ({len(train_rows)} rows)")
    print(f"[prepare_text] Wrote val to {val_file} ({len(val_rows)} rows)")

    return {
        "train": len(train_rows),
        "val": len(val_rows),
        "holdout": len(holdout_rows),
    }


if __name__ == "__main__":
    prepare_text_data(holdout_version="v2", force_rebuild=True)
