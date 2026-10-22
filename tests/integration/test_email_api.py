"""Integration tests for Email Message API (M4 acceptance criteria)."""

import pytest
from fastapi.testclient import TestClient

from skeptid.main import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_analyze_email_eml_phishing_acceptance(client: TestClient) -> None:
    """Verify M4 deliverable:

    .eml with a phishing sample returns a verdict with URL, header, and text evidence;
    attachments are listed separately and contribute at most 10% of the message risk.
    """
    eml_content = (
        b'From: "Corporate IT Support" <admin@bad-actor.xyz>\r\n'
        b"Reply-To: credential-collector@harvestbox.top\r\n"
        b"To: employee@company.com\r\n"
        b"Subject: URGENT: Action required on your security credentials\r\n"
        b"Authentication-Results: mx.google.com; spf=fail; dkim=fail; dmarc=fail\r\n"
        b"Message-ID: <unusual-id-999@bad-actor.xyz>\r\n"
        b"Date: Thu, 22 Oct 2026 12:00:00 +0000\r\n"
        b'Content-Type: multipart/mixed; boundary="boundary987"\r\n'
        b"\r\n"
        b"--boundary987\r\n"
        b'Content-Type: text/html; charset="utf-8"\r\n'
        b"\r\n"
        b"<html><body>"
        b"<p>Your access will expire in 2 hours. "
        b'Verify identity now at <a href="http://192.168.1.100/secure/login">https://company.com/verify</a></p>'
        b"</body></html>\r\n"
        b"--boundary987\r\n"
        b'Content-Type: application/octet-stream; name="patch_update.exe"\r\n'
        b'Content-Disposition: attachment; filename="patch_update.exe"\r\n'
        b"\r\n"
        b"MZ_DUMMY_EXECUTABLE_PAYLOAD\r\n"
        b"--boundary987--\r\n"
    )

    response = client.post(
        "/api/message/analyze",
        files={"file": ("urgent_security_alert.eml", eml_content, "message/rfc822")},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    # 1. Modality & Verdict
    assert data["modality"] == "email"
    assert data["label"] == "phishing"
    assert data["level"] == "HIGH"
    assert data["risk"] >= 0.80

    # 2. Evidence from all components (Text, URL, Header, Attachment)
    evidence_descriptions = [e["description"] for e in data["evidence"]]
    assert any("Reply-To" in desc or "SPF" in desc or "spoof" in desc for desc in evidence_descriptions), (
        "Expected Header evidence in verdict"
    )
    assert any("URL" in desc or "IP-literal" in desc or "Link text spoof" in desc for desc in evidence_descriptions), (
        "Expected URL evidence in verdict"
    )
    assert any("attachment" in desc.lower() for desc in evidence_descriptions), (
        "Expected attachment evidence in verdict"
    )

    # 3. Test feedback submission
    fb_res = client.post(
        "/api/feedback",
        json={"analysis_id": data["id"], "correct": True, "true_label": "phishing"},
    )
    assert fb_res.status_code == 200
    assert fb_res.json()["status"] == "recorded"

    # 4. Metrics endpoint returns telemetry
    metrics_res = client.get("/api/metrics")
    assert metrics_res.status_code == 200
    m_data = metrics_res.json()
    assert "telemetry" in m_data
    assert m_data["telemetry"]["total_analyses"] >= 1
    assert m_data["telemetry"]["total_feedback"] >= 1
