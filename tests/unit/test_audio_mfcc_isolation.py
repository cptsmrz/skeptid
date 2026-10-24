"""Unit tests for MFCC extraction, spectral metrics, and Isolation Forest audio forensics."""

import io
import wave
import numpy as np
import pytest

from skeptid.forensics.audio import (
    AudioForensicsResult,
    compute_audio_forensics,
    compute_mfcc,
    compute_spectral_centroid_and_rolloff,
    score_isolation_forest_anomaly,
)


def make_test_wav_buffer(duration_sec: float = 0.5, freq_hz: float = 440.0) -> bytes:
    sr = 16000
    n_samples = int(sr * duration_sec)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    waveform = (0.5 * np.sin(2 * np.pi * freq_hz * t) * 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(waveform.tobytes())
    return buf.getvalue()


def test_mfcc_computation() -> None:
    samples = np.random.randn(8000).astype(np.float32)
    mfccs, means, stds = compute_mfcc(samples, sr=16000, n_mfcc=13)

    assert mfccs.shape[0] == 13
    assert len(means) == 13
    assert len(stds) == 13


def test_isolation_forest_scoring() -> None:
    # 32-dim normalized feature vector
    normal_feat = np.zeros(32, dtype=np.float32)
    score, is_outlier = score_isolation_forest_anomaly(normal_feat)
    assert 0.0 <= score <= 1.0

    # Severe outlier feature vector
    outlier_feat = np.full(32, 5.0, dtype=np.float32)
    outlier_score, outlier_flag = score_isolation_forest_anomaly(outlier_feat)
    assert outlier_score > 0.40


def test_full_audio_forensics_with_mfcc_and_isolation() -> None:
    wav_bytes = make_test_wav_buffer()
    res = compute_audio_forensics(wav_bytes, filename="speech_test.wav")

    assert isinstance(res, AudioForensicsResult)
    assert "n_mfcc" in res.mfcc_summary
    assert res.mfcc_summary["n_mfcc"] == 13
    assert len(res.mfcc_summary["means"]) == 13
    assert res.spectral_centroid > 0.0
    assert res.spectral_rolloff > 0.0
    assert 0.0 <= res.isolation_forest_score <= 1.0
