"""Email header forensic heuristics.

Checks From vs Reply-To vs Return-Path domain mismatches, SPF/DKIM/DMARC status
in Authentication-Results, and missing or malformed Message-ID.
Reference: PhishSage / SKEPTID spec section 6.2.
"""

import re
from email.message import EmailMessage
from email.utils import parseaddr

from skeptid.core.types import Evidence


def _extract_domain(addr: str) -> str:
    """Extract lowercase domain name from email address."""
    if "@" in addr:
        return addr.split("@")[-1].strip().lower()
    return ""


def analyze_headers(msg: EmailMessage) -> tuple[float, list[Evidence], dict]:
    """Analyze email headers for spoofing, authentication failures, and anomalies.

    Returns:
        (header_risk: float, evidence: list[Evidence], header_details: dict)
    """
    evidence: list[Evidence] = []
    signals: list[float] = []

    # 1. Parse From, Reply-To, Return-Path
    from_raw = msg.get("From", "")
    from_name, from_addr = parseaddr(from_raw)
    from_domain = _extract_domain(from_addr)

    reply_to_raw = msg.get("Reply-To", "")
    _, reply_to_addr = parseaddr(reply_to_raw)
    reply_to_domain = _extract_domain(reply_to_addr)

    return_path_raw = msg.get("Return-Path", "")
    _, return_path_addr = parseaddr(return_path_raw)
    return_path_domain = _extract_domain(return_path_addr)

    message_id = msg.get("Message-ID", "")
    date_header = msg.get("Date", "")
    auth_results = msg.get("Authentication-Results", "")
    received_spf = msg.get("Received-SPF", "")

    header_details = {
        "from": from_addr,
        "from_domain": from_domain,
        "reply_to": reply_to_addr,
        "return_path": return_path_addr,
        "message_id": message_id,
        "auth_results": auth_results,
    }

    # Signal 1: From vs Reply-To mismatch
    if reply_to_domain and from_domain and reply_to_domain != from_domain:
        signals.append(0.70)
        evidence.append(
            Evidence(
                kind="flag",
                description=f"Reply-To domain mismatch: from '@{from_domain}' but replies route to '@{reply_to_domain}'",
                payload={
                    "indicator": "reply_to_mismatch",
                    "from_domain": from_domain,
                    "reply_to_domain": reply_to_domain,
                },
            )
        )

    # Signal 2: From vs Return-Path mismatch (when Return-Path is specified)
    if return_path_domain and from_domain and return_path_domain != from_domain:
        # High likelihood of bounce redirection or relay spoof
        signals.append(0.50)
        evidence.append(
            Evidence(
                kind="flag",
                description=f"Return-Path mismatch: from '@{from_domain}' but bounce-path is '@{return_path_domain}'",
                payload={
                    "indicator": "return_path_mismatch",
                    "from_domain": from_domain,
                    "return_path_domain": return_path_domain,
                },
            )
        )

    # Signal 3: Display Name Spoofing
    # e.g., From: "PayPal Security" <security@mail-attacker.com>
    known_brands = ["paypal", "microsoft", "google", "apple", "amazon", "chase", "wells fargo", "bank of america"]
    lower_name = from_name.lower()
    for brand in known_brands:
        if brand in lower_name and brand not in from_domain:
            signals.append(0.85)
            evidence.append(
                Evidence(
                    kind="flag",
                    description=f"Display name spoofing: name references '{brand}' but domain is '@{from_domain}'",
                    payload={"indicator": "display_name_spoof", "brand": brand, "domain": from_domain},
                )
            )

    # Signal 4: Authentication-Results (SPF, DKIM, DMARC)
    auth_lower = f"{auth_results} {received_spf}".lower()
    if "spf=fail" in auth_lower or "spf=softfail" in auth_lower:
        signals.append(0.75)
        evidence.append(
            Evidence(
                kind="flag",
                description="SPF authentication failed or softfailed",
                payload={"indicator": "spf_failure"},
            )
        )
    if "dkim=fail" in auth_lower:
        signals.append(0.75)
        evidence.append(
            Evidence(
                kind="flag",
                description="DKIM signature verification failed",
                payload={"indicator": "dkim_failure"},
            )
        )
    if "dmarc=fail" in auth_lower:
        signals.append(0.85)
        evidence.append(
            Evidence(
                kind="flag",
                description="DMARC policy check failed",
                payload={"indicator": "dmarc_failure"},
            )
        )

    # Signal 5: Missing or obviously invalid Message-ID
    if not message_id or not re.search(r"<.+@.+>", message_id):
        signals.append(0.35)
        evidence.append(
            Evidence(
                kind="flag",
                description="Missing or malformed Message-ID header",
                payload={"indicator": "missing_message_id"},
            )
        )

    # Signal 6: Missing Date header
    if not date_header:
        signals.append(0.20)

    header_risk = max(signals) if signals else 0.0
    return round(header_risk, 4), evidence, header_details
