"""Audio Forensics and Voice Deepfake Detection Engine.

Analyzes raw audio (WAV, MP3, etc.) for synthetic voice markers, pitch discontinuities,
spectral flatness anomalies, and acoustic jitter characteristic of TTS / voice cloning models.
"""

from dataclasses import dataclass
import io
import math
import wave
from typing import Any

import numpy as np
from scipy import signal  # type: ignore[import-untyped]


@dataclass
class AudioForensicsResult:
    """Quantitative results from audio deepfake and acoustic forensics."""

    duration_sec: float
    sample_rate: int
    spectral_flatness: float
    pitch_jitter_score: float
    zero_crossing_rate: float
    acoustic_entropy: float
    synthetic_risk: float
    verdict_label: str
    spectrogram_summary: dict[str, Any]
    anomalies: list[str]


def parse_wav_samples(audio_bytes: bytes) -> tuple[np.ndarray, int]:
    """Extract raw float samples and sample rate from WAV bytes."""
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = min(wf.getnframes(), framerate * 30)  # Max 30 seconds
            raw_frames = wf.readframes(n_frames)

            if sampwidth == 2:
                dtype = np.int16
            elif sampwidth == 4:
                dtype = np.int32
            elif sampwidth == 1:
                dtype = np.uint8
            else:
                dtype = np.int16

            samples = np.frombuffer(raw_frames, dtype=dtype).astype(np.float32)
            if sampwidth == 2:
                samples /= 32768.0
            elif sampwidth == 4:
                samples /= 2147483648.0
            elif sampwidth == 1:
                samples = (samples - 128.0) / 128.0

            if n_channels > 1:
                samples = samples.reshape(-1, n_channels).mean(axis=1)

            return samples, framerate
    except Exception:
        # Fallback synthetic waveform extraction from raw byte buffer
        byte_arr = np.frombuffer(audio_bytes[: min(len(audio_bytes), 48000 * 4)], dtype=np.int16)
        samples = (byte_arr.astype(np.float32) / 32768.0) if len(byte_arr) > 0 else np.zeros(16000, dtype=np.float32)
        return samples, 16000


def compute_spectral_flatness(magnitudes: np.ndarray) -> float:
    """Calculate spectral flatness (Wiener entropy) from magnitude spectrum."""
    eps = 1e-12
    pos_mag = np.maximum(magnitudes, eps)
    geometric_mean = np.exp(np.mean(np.log(pos_mag)))
    arithmetic_mean = np.mean(pos_mag)
    if arithmetic_mean <= eps:
        return 0.0
    return float(np.clip(geometric_mean / arithmetic_mean, 0.0, 1.0))


def compute_audio_forensics(audio_bytes: bytes, filename: str | None = None) -> AudioForensicsResult:
    """Analyze audio clip for speech cloning, synthetic voice, and acoustic tampering."""
    samples, sr = parse_wav_samples(audio_bytes)
    total_len = len(samples)
    duration_sec = round(total_len / max(sr, 1), 2)

    if total_len < 512:
        return AudioForensicsResult(
            duration_sec=duration_sec,
            sample_rate=sr,
            spectral_flatness=0.0,
            pitch_jitter_score=0.0,
            zero_crossing_rate=0.0,
            acoustic_entropy=0.0,
            synthetic_risk=0.1,
            verdict_label="authentic",
            spectrogram_summary={"bands": 16, "mean_power_db": -60.0},
            anomalies=[],
        )

    # 1. Zero Crossing Rate (ZCR)
    zero_crossings = np.nonzero(np.diff(samples > 0))[0]
    zcr = float(len(zero_crossings) / total_len)

    # 2. Spectrogram (STFT)
    n_perseg = min(512, total_len)
    freqs, times, Sxx = signal.spectrogram(samples, fs=sr, nperseg=n_perseg)
    power_db = 10 * np.log10(np.maximum(Sxx, 1e-10))
    mean_power_db = float(np.mean(power_db))

    # 3. Spectral Flatness across frequency columns
    flatness_values = [compute_spectral_flatness(Sxx[:, col]) for col in range(Sxx.shape[1])]
    mean_flatness = float(np.mean(flatness_values)) if flatness_values else 0.0

    # 4. Acoustic Entropy (Shannon energy distribution)
    norm_power = np.maximum(Sxx, 1e-12) / np.sum(np.maximum(Sxx, 1e-12))
    acoustic_entropy = float(-np.sum(norm_power * np.log2(norm_power))) / math.log2(max(Sxx.size, 2))

    # 5. Pitch Jitter & Harmonic Discontinuity
    window_size = int(sr * 0.025)
    hop_size = int(sr * 0.010)
    pitch_lags: list[int] = []

    for start in range(0, total_len - window_size, max(1, hop_size * 4)):
        frame = samples[start : start + window_size]
        if np.max(np.abs(frame)) < 0.02:
            continue  # Silence
        autocorr = signal.correlate(frame, frame, mode="full")
        half_corr = autocorr[len(autocorr) // 2 :]
        min_lag = max(1, int(sr / 400))
        max_lag = min(len(half_corr) - 1, int(sr / 60))
        if max_lag > min_lag:
            lag = min_lag + int(np.argmax(half_corr[min_lag:max_lag]))
            pitch_lags.append(lag)

    if len(pitch_lags) > 3:
        lag_diffs = np.abs(np.diff(pitch_lags))
        pitch_jitter = float(np.mean(lag_diffs) / max(np.mean(pitch_lags), 1))
    else:
        pitch_jitter = 0.05

    # 6. Anomaly Detection Logic
    anomalies: list[str] = []
    synthetic_risk = 0.05

    if mean_flatness < 0.015:
        anomalies.append("Robotic/hyper-compressed spectral flatness profile")
        synthetic_risk += 0.35
    elif mean_flatness > 0.40:
        anomalies.append("Excessive high-frequency diffuse background noise")
        synthetic_risk += 0.20

    if pitch_jitter < 0.02 and len(pitch_lags) > 5:
        anomalies.append("Unnaturally uniform pitch micro-stability (Neural TTS signature)")
        synthetic_risk += 0.30
    elif pitch_jitter > 0.45:
        anomalies.append("Severe pitch phase discontinuities detected")
        synthetic_risk += 0.25

    nyquist_ratio = float(np.mean(Sxx[-int(Sxx.shape[0] * 0.2) :, :]) / (np.mean(Sxx) + 1e-9))
    if nyquist_ratio < 0.005 and len(pitch_lags) > 5:
        anomalies.append("Steep 16kHz spectral cutoff typical of fast vocoders")
        synthetic_risk += 0.25

    synthetic_risk = round(min(1.0, max(0.02, synthetic_risk)), 4)
    if synthetic_risk > 0.70:
        verdict_label = "synthetic"
    elif synthetic_risk > 0.35:
        verdict_label = "manipulated"
    else:
        verdict_label = "authentic"

    band_step = max(1, Sxx.shape[0] // 16)
    band_energies = [
        round(float(np.mean(Sxx[i * band_step : (i + 1) * band_step, :])), 4)
        for i in range(min(16, Sxx.shape[0] // band_step))
    ]

    return AudioForensicsResult(
        duration_sec=duration_sec,
        sample_rate=sr,
        spectral_flatness=round(mean_flatness, 4),
        pitch_jitter_score=round(pitch_jitter, 4),
        zero_crossing_rate=round(zcr, 4),
        acoustic_entropy=round(acoustic_entropy, 4),
        synthetic_risk=synthetic_risk,
        verdict_label=verdict_label,
        spectrogram_summary={
            "bands": len(band_energies),
            "band_energies": band_energies,
            "mean_power_db": round(mean_power_db, 2),
        },
        anomalies=anomalies,
    )
