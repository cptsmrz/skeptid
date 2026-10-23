"""Unit tests for Audio and Binary Hex forensics engines."""

import io
import wave
import pytest

from skeptid.api.validators import detect_media_type
from skeptid.core.orchestrator import Orchestrator
from skeptid.core.types import Modality
from skeptid.engines.audio import AudioEngine
from skeptid.engines.binary import BinaryEngine
from skeptid.forensics.audio import compute_audio_forensics
from skeptid.forensics.hex import analyze_binary_hex, compute_shannon_entropy


def make_dummy_wav() -> bytes:
    """Create a minimal 0.25s 16kHz WAV buffer."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # 4000 samples of a 440 Hz tone
        raw_samples = bytearray(8000)
        wf.writeframes(bytes(raw_samples))
    return buf.getvalue()


def test_audio_forensics_computation() -> None:
    wav_bytes = make_dummy_wav()
    res = compute_audio_forensics(wav_bytes, filename="test.wav")
    assert res.duration_sec >= 0.2
    assert res.sample_rate == 16000
    assert 0.0 <= res.synthetic_risk <= 1.0
    assert res.verdict_label in ("authentic", "manipulated", "synthetic")
    assert "band_energies" in res.spectrogram_summary


def test_binary_hex_entropy() -> None:
    # Repetitive bytes = low entropy
    low_entropy_bytes = b"A" * 1000
    low_ent = compute_shannon_entropy(low_entropy_bytes)
    assert low_ent == 0.0

    # Random bytes = high entropy
    import os
    rand_bytes = os.urandom(1000)
    high_ent = compute_shannon_entropy(rand_bytes)
    assert high_ent > 7.0

    res = analyze_binary_hex(b"MZ\x90\x00" + b"powershell -enc test", filename="payload.exe")
    assert res.detected_signature == "PE_EXECUTABLE"
    assert res.risk_score >= 0.30
    assert res.verdict_label in ("suspicious", "malicious")


def test_detect_media_type_audio() -> None:
    wav_bytes = make_dummy_wav()
    m_type, fmt = detect_media_type(wav_bytes)
    assert m_type == "audio"
    assert fmt == "wav"

    mp3_bytes = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 20
    m_type, fmt = detect_media_type(mp3_bytes)
    assert m_type == "audio"
    assert fmt == "mp3"

    raw_bin = b"\x7fELF" + b"\x00" * 30
    with pytest.raises(Exception) as excinfo:
        detect_media_type(raw_bin)
    assert "Unsupported media format" in str(excinfo.value)


@pytest.mark.asyncio
async def test_audio_engine_verdict() -> None:
    orchestrator = Orchestrator()
    engine = AudioEngine(orchestrator)
    wav_bytes = make_dummy_wav()
    verdict = await engine.analyze(wav_bytes, filename="sample.wav", use_external=False)

    assert verdict.modality == Modality.AUDIO
    assert 0.0 <= verdict.risk <= 1.0
    assert len(verdict.providers) >= 2
    assert any(ev.kind == "spectrum" for ev in verdict.evidence)
    assert any(ev.kind == "metric" for ev in verdict.evidence)


@pytest.mark.asyncio
async def test_binary_engine_verdict() -> None:
    orchestrator = Orchestrator()
    engine = BinaryEngine(orchestrator)
    data = b"PK\x03\x04" + b"\x00" * 100
    verdict = await engine.analyze(data, filename="archive.zip")

    assert verdict.modality == Modality.BINARY
    assert 0.0 <= verdict.risk <= 1.0
    assert any(ev.kind == "hex_entropy" for ev in verdict.evidence)
