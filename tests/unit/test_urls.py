"""Unit tests for URL forensics."""

from skeptid.forensics.urls import analyze_urls, extract_urls


def test_extract_urls() -> None:
    text = "Visit http://example.com/login or check https://safe.org for info."
    urls = extract_urls(text)
    assert len(urls) == 2
    assert "http://example.com/login" in urls
    assert "https://safe.org" in urls


def test_ip_literal_host() -> None:
    text = "Click here: http://192.168.1.50/account/verify"
    risk, evidence, _details = analyze_urls(text)
    assert risk >= 0.80
    assert any(ev.payload.get("indicator") == "ip_literal_host" for ev in evidence)


def test_punycode_homoglyph() -> None:
    text = "Login to your account: https://xn--pple-43d.com/login"
    risk, evidence, _details = analyze_urls(text)
    assert risk >= 0.80
    assert any(ev.payload.get("indicator") == "punycode" for ev in evidence)


def test_url_shortener() -> None:
    text = "Check out your prize: http://bit.ly/3x8AbCd"
    risk, evidence, _details = analyze_urls(text)
    assert risk >= 0.50
    assert any(ev.payload.get("indicator") == "shortener" for ev in evidence)


def test_excessive_subdomains() -> None:
    text = "Update credentials: https://secure.login.verify.account.chase.badsite.com/auth"
    risk, evidence, _details = analyze_urls(text)
    assert risk >= 0.50
    assert any(ev.payload.get("indicator") == "excessive_subdomains" for ev in evidence)


def test_suspicious_tld() -> None:
    text = "Claim your bonus now at http://free-crypto-giveaway.xyz/claim"
    risk, evidence, _details = analyze_urls(text)
    assert risk >= 0.60
    assert any(ev.payload.get("indicator") == "suspicious_tld" for ev in evidence)


def test_display_text_mismatch() -> None:
    html = '<p>Verify your account at <a href="http://evil-attacker.top/login">https://paypal.com/signin</a></p>'
    risk, evidence, _details = analyze_urls("", html=html)
    assert risk >= 0.90
    assert any(ev.payload.get("indicator") == "href_mismatch" for ev in evidence)
