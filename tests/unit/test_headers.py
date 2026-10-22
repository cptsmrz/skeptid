"""Unit tests for email header forensics."""

import email
from email import policy

from skeptid.forensics.headers import analyze_headers


def test_clean_headers() -> None:
    raw = (
        "From: Alice <alice@example.com>\r\n"
        "To: Bob <bob@example.com>\r\n"
        "Reply-To: alice@example.com\r\n"
        "Subject: Meeting notes\r\n"
        "Message-ID: <12345@example.com>\r\n"
        "Date: Thu, 22 Oct 2026 10:00:00 +0000\r\n"
        "\r\n"
        "Hi Bob, here are the notes."
    )
    msg = email.message_from_string(raw, policy=policy.default)
    risk, evidence, _details = analyze_headers(msg)
    assert risk < 0.35
    assert len(evidence) == 0


def test_reply_to_mismatch() -> None:
    raw = (
        "From: Official Support <support@legit-service.com>\r\n"
        "Reply-To: attacker-collector@harvest-box.xyz\r\n"
        "Subject: Security update\r\n"
        "Message-ID: <msg999@legit-service.com>\r\n"
        "Date: Thu, 22 Oct 2026 10:00:00 +0000\r\n"
        "\r\n"
        "Please reply with your access code."
    )
    msg = email.message_from_string(raw, policy=policy.default)
    risk, evidence, _details = analyze_headers(msg)
    assert risk >= 0.70
    assert any(ev.payload.get("indicator") == "reply_to_mismatch" for ev in evidence)


def test_auth_results_failures() -> None:
    raw = (
        "From: Billing <billing@example.com>\r\n"
        "Subject: Overdue notice\r\n"
        "Authentication-Results: mx.google.com; spf=fail; dkim=fail; dmarc=fail\r\n"
        "Message-ID: <001@example.com>\r\n"
        "Date: Thu, 22 Oct 2026 10:00:00 +0000\r\n"
        "\r\n"
        "Pay now."
    )
    msg = email.message_from_string(raw, policy=policy.default)
    risk, evidence, _details = analyze_headers(msg)
    assert risk >= 0.75
    assert any(ev.payload.get("indicator") == "spf_failure" for ev in evidence)
    assert any(ev.payload.get("indicator") == "dkim_failure" for ev in evidence)
    assert any(ev.payload.get("indicator") == "dmarc_failure" for ev in evidence)


def test_display_name_spoofing() -> None:
    raw = (
        'From: "PayPal Account Security" <user48102@scam-server.net>\r\n'
        "Subject: Your PayPal account has been limited\r\n"
        "Message-ID: <abc@scam-server.net>\r\n"
        "Date: Thu, 22 Oct 2026 10:00:00 +0000\r\n"
        "\r\n"
        "Log in immediately."
    )
    msg = email.message_from_string(raw, policy=policy.default)
    risk, evidence, _details = analyze_headers(msg)
    assert risk >= 0.80
    assert any(ev.payload.get("indicator") == "display_name_spoof" for ev in evidence)
