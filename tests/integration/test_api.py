"""Integration tests for FastAPI endpoints with mock providers."""

import pytest
from fastapi.testclient import TestClient

from skeptid.core.config import ModalityConfig, SkeptidConfig
from skeptid.core.orchestrator import Orchestrator
from skeptid.core.types import Modality
from skeptid.main import create_app
from skeptid.providers.mock import MockProvider


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_healthz_endpoint(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"


def test_analyze_message_json_success(client: TestClient) -> None:
    payload = {"text": "URGENT: Your account has been suspended. Click here to login."}
    resp = client.post("/api/message/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    # Validate schema fields
    assert "id" in data
    assert data["modality"] == "text"
    assert "label" in data
    assert 0.0 <= data["risk"] <= 1.0
    assert data["level"] in ["LOW", "MEDIUM", "HIGH"]
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["disagreement"], bool)
    assert data["mock"] is True
    assert len(data["providers"]) >= 1
    assert data["limits_note"] == "Risk score with evidence, not proof."


def test_analyze_message_multipart_txt(client: TestClient) -> None:
    files = {"file": ("sample.txt", b"Suspicious account activity detected.", "text/plain")}
    resp = client.post("/api/message/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["modality"] == "text"
    assert "label" in data


def test_analyze_message_multipart_eml(client: TestClient) -> None:
    eml_content = (
        b"From: security@fake-bank.com\r\n"
        b"To: victim@example.com\r\n"
        b"Subject: Urgent security alert\r\n"
        b"\r\n"
        b"Please reset your password immediately at http://phishing.evil/login\r\n"
    )
    files = {"file": ("alert.eml", eml_content, "message/rfc822")}
    resp = client.post("/api/message/analyze", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["modality"] == "email"
    assert "label" in data


def test_analyze_message_validation_failure(client: TestClient) -> None:
    resp = client.post("/api/message/analyze", json={"text": "   "})
    assert resp.status_code == 400


def test_analyze_message_unsupported_file(client: TestClient) -> None:
    files = {"file": ("malware.exe", b"binary content", "application/octet-stream")}
    resp = client.post("/api/message/analyze", files=files)
    assert resp.status_code == 400
    assert "Allowed: .eml, .txt" in resp.json()["detail"]


def test_analyze_message_all_providers_fail_returns_503() -> None:
    cfg = SkeptidConfig(
        text=ModalityConfig(primary="p1", chain=["p1"], timeout_s=1.0)
    )
    failing_provider = MockProvider("p1", Modality.TEXT, force_error="Provider failure")
    orchestrator = Orchestrator(
        config=cfg,
        providers={Modality.TEXT: {"p1": failing_provider}},
    )
    app = create_app(config=cfg)
    app.state.orchestrator = orchestrator

    with TestClient(app) as custom_client:
        resp = custom_client.post("/api/message/analyze", json={"text": "Any text"})
        assert resp.status_code == 503
        assert "All analysis providers failed" in resp.json()["detail"]


def test_feedback_endpoint(client: TestClient) -> None:
    fb_payload = {
        "analysis_id": "test-uuid-1234",
        "correct": False,
        "true_label": "safe",
    }
    resp = client.post("/api/feedback", json=fb_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "recorded"
    assert data["analysis_id"] == "test-uuid-1234"


def test_metrics_endpoint(client: TestClient) -> None:
    resp = client.get("/api/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    assert "promotions" in data


def test_providers_status_endpoint(client: TestClient) -> None:
    resp = client.get("/api/providers/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    for item in data["providers"]:
        assert "id" in item
        assert "modality" in item
        assert item["status"] in ["up", "down"]
        # Ensure no secret or internal URL is exposed
        assert "http" not in item.values()
        assert "key" not in item
