"""Unit tests for core types and contracts."""

from skeptid.core.types import (
    IMAGE_LABELS,
    TEXT_LABELS,
    AnalysisInput,
    Evidence,
    Modality,
    ProviderResult,
)


def test_modalities_and_labels() -> None:
    assert Modality.TEXT.value == "text"
    assert Modality.EMAIL.value == "email"
    assert Modality.IMAGE.value == "image"
    assert Modality.VIDEO.value == "video"
    assert Modality.AUDIO.value == "audio"

    assert TEXT_LABELS == ["safe", "phishing", "spam", "threat", "bullying"]
    assert IMAGE_LABELS == ["authentic", "filtered", "ai_edited", "ai_generated"]


def test_evidence_instantiation() -> None:
    ev = Evidence(
        kind="span",
        description="Suspicious urgency keyword",
        payload={"start": 10, "end": 25, "weight": 0.85},
    )
    assert ev.kind == "span"
    assert ev.description == "Suspicious urgency keyword"
    assert ev.payload["start"] == 10
    assert ev.payload["weight"] == 0.85


def test_provider_result_structure() -> None:
    res = ProviderResult(
        provider_id="own",
        ok=True,
        label_scores={"safe": 0.1, "phishing": 0.9},
        risk=0.9,
        evidence=[],
        latency_ms=15,
        model_version="mock",
    )
    assert res.provider_id == "own"
    assert res.ok is True
    assert res.risk == 0.9
    assert res.error is None


def test_analysis_input_defaults() -> None:
    inp = AnalysisInput(modality=Modality.TEXT, text="Hello world")
    assert inp.modality == Modality.TEXT
    assert inp.text == "Hello world"
    assert inp.raw_bytes is None
    assert inp.metadata == {}
