"""Unit tests for the Email Engine and in-lane email fusion."""

import pytest

from skeptid.core.config import SkeptidConfig
from skeptid.core.orchestrator import Orchestrator
from skeptid.core.types import TEXT_LABELS, AnalysisInput, Modality, ProviderResult
from skeptid.engines.email import EmailEngine


class MockTextAnalysisProvider:
    id = "mock_text"

    async def health(self) -> bool:
        return True

    async def analyze(self, payload: AnalysisInput) -> ProviderResult:
        text = (payload.text or "").lower()
        if "suspended" in text or "urgent" in text:
            return ProviderResult(
                provider_id=self.id,
                ok=True,
                label_scores={"safe": 0.05, "phishing": 0.90, "spam": 0.05, "bullying": 0.0, "threat": 0.0},
                risk=0.90,
                evidence=[],
                coverage=list(TEXT_LABELS),
                latency_ms=1,
                model_version="test_mock",
            )
        return ProviderResult(
            provider_id=self.id,
            ok=True,
            label_scores={"safe": 0.95, "phishing": 0.02, "spam": 0.02, "bullying": 0.005, "threat": 0.005},
            risk=0.05,
            evidence=[],
            coverage=list(TEXT_LABELS),
            latency_ms=1,
            model_version="test_mock",
        )


@pytest.fixture
def email_engine() -> EmailEngine:
    cfg = SkeptidConfig()
    cfg.text.chain = ["mock_text"]
    cfg.text.primary = "mock_text"
    provider = MockTextAnalysisProvider()
    orchestrator = Orchestrator(
        config=cfg,
        providers={
            Modality.TEXT: {"mock_text": provider},  # type: ignore[dict-item]
            Modality.EMAIL: {"mock_text": provider},  # type: ignore[dict-item]
        },
    )
    return EmailEngine(orchestrator=orchestrator)


@pytest.mark.asyncio
async def test_email_engine_clean_message(email_engine: EmailEngine) -> None:
    eml = (
        b"From: colleague@company.org\r\n"
        b"To: me@company.org\r\n"
        b"Subject: Lunch plans\r\n"
        b"Message-ID: <clean123@company.org>\r\n"
        b"Date: Thu, 22 Oct 2026 12:00:00 +0000\r\n"
        b"\r\n"
        b"Hey, see you in the cafeteria at 12:30pm!\r\n"
    )
    verdict = await email_engine.analyze(eml, filename="lunch.eml")
    assert verdict.modality == Modality.EMAIL
    assert verdict.risk < 0.35
    assert verdict.level == "LOW"


@pytest.mark.asyncio
async def test_email_engine_phishing_signals(email_engine: EmailEngine) -> None:
    eml = (
        b'From: "PayPal Support" <billing@attacker-domain.xyz>\r\n'
        b"Reply-To: harvest@harvestbox.top\r\n"
        b"To: victim@example.com\r\n"
        b"Subject: URGENT: Verify your account\r\n"
        b"Authentication-Results: mx.example.com; spf=fail; dkim=fail\r\n"
        b"Message-ID: <suspicious-id@bad>\r\n"
        b"Date: Thu, 22 Oct 2026 12:00:00 +0000\r\n"
        b"\r\n"
        b"Your account will be suspended! Click http://192.168.1.1/login.php immediately!\r\n"
    )
    verdict = await email_engine.analyze(eml, filename="phish.eml")
    assert verdict.modality == Modality.EMAIL
    assert verdict.risk >= 0.80  # Floor rule triggered by URL (IP-literal) or headers
    assert verdict.label == "phishing"
    assert verdict.level == "HIGH"

    # Evidence must contain URL and header flags
    kinds = [e.kind for e in verdict.evidence]
    assert "flag" in kinds
    indicators = [e.payload.get("indicator") for e in verdict.evidence if isinstance(e.payload, dict)]
    assert any("ip_literal" in ind or "reply_to" in ind or "spoof" in ind for ind in indicators if ind)


@pytest.mark.asyncio
async def test_email_dangerous_extension(email_engine: EmailEngine) -> None:
    """Test detection of dangerous executable attachments (.exe, .scr, .vbs)."""
    eml = (
        b"From: billing@vendor.com\r\n"
        b"To: user@company.com\r\n"
        b"Subject: Overdue Bill\r\n"
        b'Content-Type: multipart/mixed; boundary="sep"\r\n'
        b"\r\n"
        b"--sep\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Please review statement.\r\n"
        b"--sep\r\n"
        b'Content-Type: application/octet-stream; name="statement.scr"\r\n'
        b'Content-Disposition: attachment; filename="statement.scr"\r\n'
        b"\r\n"
        b"BINARY_PAYLOAD\r\n"
        b"--sep--\r\n"
    )
    verdict = await email_engine.analyze(eml, filename="statement.eml")
    assert any(
        e.payload.get("indicator") == "dangerous_extension"
        and e.payload.get("extension") == ".scr"
        for e in verdict.evidence
    )
    assert verdict.risk >= 0.80


@pytest.mark.asyncio
async def test_email_href_mismatch(email_engine: EmailEngine) -> None:
    """Test detection of anchor href targeting malicious domain while display text shows benign."""
    eml = (
        b"From: support@paypal.com\r\n"
        b"To: user@example.com\r\n"
        b"Subject: Account Security Alert\r\n"
        b'Content-Type: multipart/alternative; boundary="alt"\r\n'
        b"\r\n"
        b"--alt\r\n"
        b"Content-Type: text/plain\r\n"
        b"\r\n"
        b"Please verify your account.\r\n"
        b"--alt\r\n"
        b"Content-Type: text/html\r\n"
        b"\r\n"
        b'<p>Click here to login: <a href="http://evil-attacker.top/login">https://paypal.com/signin</a></p>\r\n'
        b"--alt--\r\n"
    )
    verdict = await email_engine.analyze(eml, filename="spoofed_link.eml")
    assert any(e.payload.get("indicator") == "href_mismatch" for e in verdict.evidence)
    assert verdict.risk >= 0.80
    assert verdict.label == "phishing"


@pytest.mark.asyncio
async def test_email_spf_fail(email_engine: EmailEngine) -> None:
    """Test parsing of Authentication-Results SPF and DKIM failures."""
    eml = (
        b"From: security@chase.com\r\n"
        b"To: customer@example.com\r\n"
        b"Subject: Notice\r\n"
        b"Authentication-Results: mx.receiver.com; spf=fail smtp.mailfrom=chase.com; dkim=neutral\r\n"
        b"\r\n"
        b"Please check your recent transactions.\r\n"
    )
    verdict = await email_engine.analyze(eml, filename="spf_fail.eml")
    assert any(e.payload.get("indicator") == "spf_failure" for e in verdict.evidence)
    assert any("SPF authentication failed" in e.description for e in verdict.evidence)


@pytest.mark.asyncio
async def test_email_attachment_cap(email_engine: EmailEngine) -> None:
    """Test that email attachment parsing is capped at MAX_ATTACHMENTS (3)."""
    eml = (
        b"From: files@share.com\r\n"
        b"Subject: 5 files attached\r\n"
        b'Content-Type: multipart/mixed; boundary="boundary_multi"\r\n'
        b"\r\n"
        b"--boundary_multi\r\n"
        b"Content-Type: text/plain\r\n\r\nHere are the files.\r\n"
        b"--boundary_multi\r\n"
        b'Content-Type: text/plain; name="file1.txt"\r\n\r\nContent 1\r\n'
        b"--boundary_multi\r\n"
        b'Content-Type: text/plain; name="file2.txt"\r\n\r\nContent 2\r\n'
        b"--boundary_multi\r\n"
        b'Content-Type: text/plain; name="file3.txt"\r\n\r\nContent 3\r\n'
        b"--boundary_multi\r\n"
        b'Content-Type: text/plain; name="file4.txt"\r\n\r\nContent 4\r\n'
        b"--boundary_multi--\r\n"
    )
    _, _, _, raw_attachments = email_engine.parse_eml(eml)
    assert len(raw_attachments) == 3
    filenames = [a["filename"] for a in raw_attachments]
    assert filenames == ["file1.txt", "file2.txt", "file3.txt"]


@pytest.mark.asyncio
async def test_email_floor_rule(email_engine: EmailEngine) -> None:
    """Test floor rule: if any present component >= 0.90, final risk >= 0.80."""
    # Body is clean (risk=0.05 from MockTextAnalysisProvider), but href mismatch triggers URL risk=0.95
    eml = (
        b"From: colleague@company.org\r\n"
        b"Subject: Team Lunch\r\n"
        b'Content-Type: multipart/alternative; boundary="part"\r\n'
        b"\r\n"
        b"--part\r\n"
        b"Content-Type: text/plain\r\n\r\nJoin us for lunch today!\r\n"
        b"--part\r\n"
        b"Content-Type: text/html\r\n\r\n"
        b'<p>View menu: <a href="http://malicious-creds-stealer.xyz">https://cafeteria.internal/menu</a></p>\r\n'
        b"--part--\r\n"
    )
    verdict = await email_engine.analyze(eml, filename="floor.eml")
    # Even though body risk is ~0.05 with 60% weight, component floor enforces >= 0.80
    assert verdict.risk >= 0.80
    assert verdict.level == "HIGH"
