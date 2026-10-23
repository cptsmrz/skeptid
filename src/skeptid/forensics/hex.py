"""Binary and Raw Byte Forensics Engine.

Inspects byte-level entropy, byte distributions, file signature anomalies,
hidden embedded payloads, and extracted indicators from raw binary files.
"""

from collections import Counter
from dataclasses import dataclass
import math
import re
from typing import Any


@dataclass
class BinaryHexResult:
    """Quantitative results from raw byte-level forensics."""

    size_bytes: int
    shannon_entropy: float
    detected_signature: str
    extension_mismatch: bool
    suspicious_strings: list[str]
    entropy_profile: list[float]  # 16-segment entropy curve
    is_packed_or_encrypted: bool
    risk_score: float
    verdict_label: str
    byte_histogram: list[int]  # 16 bins


MAGIC_SIGNATURES: dict[str, bytes] = {
    "PE_EXECUTABLE": b"MZ",
    "ELF_EXECUTABLE": b"\x7fELF",
    "MACHO_32": b"\xfe\xed\xfa\xce",
    "MACHO_64": b"\xfe\xed\xfa\xcf",
    "ZIP_ARCHIVE": b"PK\x03\x04",
    "PDF_DOCUMENT": b"%PDF",
    "JPEG_IMAGE": b"\xff\xd8\xff",
    "PNG_IMAGE": b"\x89PNG\r\n\x1a\n",
    "GIF_IMAGE": b"GIF8",
    "WEBP_IMAGE": b"RIFF",
    "SHELL_SCRIPT": b"#!",
}


def compute_shannon_entropy(data: bytes) -> float:
    """Compute Shannon entropy in bits per byte (0.0 to 8.0)."""
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values())
    return float(round(entropy, 4))


def extract_ascii_strings(data: bytes, min_len: int = 5, max_strings: int = 20) -> list[str]:
    """Extract printable ASCII strings from binary blob."""
    pattern = re.compile(rb"[\x20-\x7E]{" + str(min_len).encode() + rb",}")
    matches = pattern.findall(data)
    results: list[str] = []
    suspicious_keywords = {
        "http://", "https://", "eval(", "cmd.exe", "powershell", "system(",
        "/bin/sh", "/bin/bash", "base64", "socket", "connect", "wget ", "curl "
    }

    for m in matches:
        s = m.decode("ascii", errors="ignore").strip()
        lower_s = s.lower()
        if any(kw in lower_s for kw in suspicious_keywords) or len(results) < max_strings:
            results.append(s[:120])
            if len(results) >= max_strings:
                break
    return results


def analyze_binary_hex(data: bytes, filename: str | None = None) -> BinaryHexResult:
    """Analyze raw binary file for obfuscation, high entropy, and malicious indicators."""
    size = len(data)
    overall_entropy = compute_shannon_entropy(data)

    # 1. Signature identification
    detected_sig = "UNKNOWN_BINARY"
    for name, magic in MAGIC_SIGNATURES.items():
        if data.startswith(magic):
            detected_sig = name
            break

    # 2. Extension Mismatch Detection
    ext_mismatch = False
    if filename:
        fn_lower = filename.lower()
        if (fn_lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")) and
                detected_sig in ("PE_EXECUTABLE", "ELF_EXECUTABLE", "ZIP_ARCHIVE", "SHELL_SCRIPT")):
            ext_mismatch = True
        elif fn_lower.endswith(".pdf") and detected_sig in ("PE_EXECUTABLE", "ELF_EXECUTABLE"):
            ext_mismatch = True

    # 3. 16-Segment Entropy Profile (identifying dense encrypted chunks or hidden sections)
    segment_size = max(64, size // 16)
    entropy_profile: list[float] = []
    for i in range(16):
        start = i * segment_size
        end = min(size, (i + 1) * segment_size)
        if start < size:
            entropy_profile.append(compute_shannon_entropy(data[start:end]))
        else:
            entropy_profile.append(overall_entropy)

    # 4. Byte Histogram (16 buckets of 16 values)
    counts = Counter(data)
    byte_hist: list[int] = []
    for b in range(16):
        bucket_sum = sum(counts[val] for val in range(b * 16, (b + 1) * 16))
        byte_hist.append(bucket_sum)

    # 5. Suspicious strings
    suspicious_strings = extract_ascii_strings(data)

    # 6. Risk Scoring
    risk = 0.05
    is_packed = overall_entropy > 7.4 or any(e > 7.75 for e in entropy_profile)

    if ext_mismatch:
        risk += 0.50
    if is_packed:
        risk += 0.35
    if detected_sig in ("PE_EXECUTABLE", "ELF_EXECUTABLE", "SHELL_SCRIPT"):
        risk += 0.30
    if any(re.search(r"https?://|powershell|cmd\.exe|/bin/sh", s, re.I) for s in suspicious_strings):
        risk += 0.25

    risk = round(min(1.0, max(0.02, risk)), 4)
    if risk > 0.70:
        verdict = "malicious"
    elif risk > 0.35:
        verdict = "suspicious"
    else:
        verdict = "clean"

    return BinaryHexResult(
        size_bytes=size,
        shannon_entropy=overall_entropy,
        detected_signature=detected_sig,
        extension_mismatch=ext_mismatch,
        suspicious_strings=suspicious_strings[:10],
        entropy_profile=entropy_profile,
        is_packed_or_encrypted=is_packed,
        risk_score=risk,
        verdict_label=verdict,
        byte_histogram=byte_hist,
    )
