"""URL forensic heuristics for email and text analysis.

Detects IP-literal hosts, punycode/homoglyphs, URL shorteners, excessive subdomains,
suspicious top-level domains, and display-text vs href mismatches.
Reference: PhishSage / SKEPTID spec section 6.2.
"""

import ipaddress
import re
from urllib.parse import urlparse

from skeptid.core.types import Evidence

KNOWN_SHORTENERS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "ow.ly",
    "is.gd",
    "buff.ly",
    "adf.ly",
    "bitly.com",
    "goo.gl",
    "rebrand.ly",
    "cutt.ly",
    "rb.gy",
}

SUSPICIOUS_TLDS = {
    "xyz",
    "top",
    "click",
    "loan",
    "work",
    "gq",
    "cf",
    "ml",
    "tk",
    "zip",
    "mov",
    "buzz",
    "racing",
    "cam",
    "country",
    "stream",
    "surf",
    "icu",
    "rest",
}

URL_REGEX = re.compile(
    r"""(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'".,<>?«»“”‘’]))""",
    re.VERBOSE,
)

MARKDOWN_LINK_REGEX = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)", re.IGNORECASE)
HTML_LINK_REGEX = re.compile(
    r"""<a\s+(?:[^>]*?\s+)?href=["']([^"']*)["'][^>]*>(.*?)</a>""", re.IGNORECASE | re.DOTALL
)


def extract_urls(text: str) -> list[str]:
    """Extract raw URLs from plaintext."""
    matches = URL_REGEX.findall(text)
    urls: list[str] = []
    for match in matches:
        raw = match[0] if isinstance(match, tuple) else match
        if not raw.startswith(("http://", "https://")):
            raw = "http://" + raw
        urls.append(raw)
    return urls


def analyze_urls(text: str, html: str | None = None) -> tuple[float, list[Evidence], list[dict]]:
    """Analyze all URLs in message text and optional HTML for phishing signals.

    Returns:
        (url_risk: float, evidence: list[Evidence], url_details: list[dict])
    """
    raw_urls = extract_urls(text)
    if html:
        raw_urls.extend(extract_urls(html))

    # Also detect href vs display-text mismatches
    mismatches: list[dict[str, str]] = []
    if html:
        for match in HTML_LINK_REGEX.finditer(html):
            href = match.group(1).strip()
            display_text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            if URL_REGEX.match(display_text):
                # Display looks like a URL
                parsed_href = urlparse(href if href.startswith("http") else "http://" + href)
                parsed_display = urlparse(
                    display_text if display_text.startswith("http") else "http://" + display_text
                )
                if (
                    parsed_href.netloc
                    and parsed_display.netloc
                    and parsed_href.netloc.lower() != parsed_display.netloc.lower()
                ):
                    mismatches.append({"display": display_text, "href": href})

    for match in MARKDOWN_LINK_REGEX.finditer(text):
        display = match.group(1).strip()
        href = match.group(2).strip()
        if URL_REGEX.match(display):
            parsed_href = urlparse(href)
            parsed_display = urlparse(
                display if display.startswith("http") else "http://" + display
            )
            if (
                parsed_href.netloc
                and parsed_display.netloc
                and parsed_href.netloc.lower() != parsed_display.netloc.lower()
            ):
                mismatches.append({"display": display, "href": href})

    if not raw_urls and not mismatches:
        return 0.0, [], []

    url_details: list[dict] = []
    evidence: list[Evidence] = []
    signals: list[float] = []

    seen = set()
    for raw in raw_urls:
        if raw in seen:
            continue
        seen.add(raw)

        try:
            parsed = urlparse(raw)
            host = (parsed.hostname or "").lower()
        except ValueError:
            continue

        flags: list[str] = []
        item_risk = 0.0

        # 1. IP-literal host
        try:
            ipaddress.ip_address(host)
            flags.append("ip_literal_host")
            item_risk = max(item_risk, 0.85)
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"IP-literal URL host: {raw}",
                    payload={"url": raw, "indicator": "ip_literal_host"},
                )
            )
        except ValueError:
            pass

        # 2. Punycode / Internationalized domain homoglyph
        if "xn--" in host:
            flags.append("punycode_homoglyph")
            item_risk = max(item_risk, 0.80)
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"Punycode homoglyph detected: {host}",
                    payload={"url": raw, "indicator": "punycode"},
                )
            )

        # 3. Known URL shortener
        if host in KNOWN_SHORTENERS:
            flags.append("shortener")
            item_risk = max(item_risk, 0.50)
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"URL shortener obfuscating destination: {host}",
                    payload={"url": raw, "indicator": "shortener"},
                )
            )

        # 4. Excessive subdomains (>= 3 parts before domain)
        parts = host.split(".")
        if len(parts) >= 4 and not parts[-1].isdigit():
            flags.append("excessive_subdomains")
            item_risk = max(item_risk, 0.55)
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"Excessive subdomains: {host}",
                    payload={
                        "url": raw,
                        "indicator": "excessive_subdomains",
                        "subdomains": parts[:-2],
                    },
                )
            )

        # 5. Suspicious TLD
        tld = parts[-1] if parts else ""
        if tld in SUSPICIOUS_TLDS:
            flags.append(f"suspicious_tld_{tld}")
            item_risk = max(item_risk, 0.65)
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"High-abuse top-level domain: .{tld}",
                    payload={"url": raw, "indicator": "suspicious_tld", "tld": tld},
                )
            )

        signals.append(item_risk)
        url_details.append(
            {
                "url": raw,
                "host": host,
                "flags": flags,
                "risk": item_risk,
            }
        )

    # Mismatches (critical phishing signal)
    for mm in mismatches:
        signals.append(0.95)
        evidence.append(
            Evidence(
                kind="flag",
                description=f"Link text spoof: displayed '{mm['display']}' points to '{mm['href']}'",
                payload={
                    "indicator": "href_mismatch",
                    "display": mm["display"],
                    "href": mm["href"],
                },
            )
        )
        url_details.append(
            {
                "url": mm["href"],
                "flags": ["display_text_mismatch"],
                "risk": 0.95,
                "display": mm["display"],
            }
        )

    overall_url_risk = max(signals) if signals else 0.0
    return round(overall_url_risk, 4), evidence, url_details
