"""Rule-based forensic lexicon scanner for suspicious patterns in text."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LexiconHit:
    """Represents a matched rule pattern in text."""

    category: str
    term: str
    start: int
    end: int
    description: str
    weight: float


# Regex patterns matching key suspicious indicators
_PATTERNS: dict[str, list[tuple[re.Pattern[str], str, float]]] = {
    "urgency": [
        (re.compile(r"\b(urgent(ly)?|immediate(ly)?)\b", re.IGNORECASE), "High-urgency language", 0.35),
        (re.compile(r"\b(action required|act now|within \d+\s*(hours?|mins?|days?))\b", re.IGNORECASE), "Time-pressure call to action", 0.40),
        (re.compile(r"\b(account (has been )?suspended|account (will be )?terminated|security alert)\b", re.IGNORECASE), "Urgent account suspension threat", 0.50),
    ],
    "credentials": [
        (re.compile(r"\b(verify|confirm|reset|update)\s+(your\s+)?(password|passcode|pin|credentials)\b", re.IGNORECASE), "Credential verification prompt", 0.65),
        (re.compile(r"\b(social security( number)?|ssn|credit card|cvv|bank account)\b", re.IGNORECASE), "Sensitive financial/PII request", 0.70),
        (re.compile(r"\b(click here to (log ?in|verify|authenticate))\b", re.IGNORECASE), "Call-to-action login link text", 0.55),
    ],
    "threat": [
        (re.compile(r"\b(i will|we will|gonna)\s+(kill|harm|destroy|hurt|attack|murder)\s+(you|your)\b", re.IGNORECASE), "Direct physical threat of violence", 0.85),
        (re.compile(r"\b(watch your back|you will pay|you('re| are) dead)\b", re.IGNORECASE), "Intimidating threat indicator", 0.75),
    ],
    "bullying": [
        (re.compile(r"\b(kill your\s?self|die in a fire|nobody likes you|jump off a bridge)\b", re.IGNORECASE), "Severe abusive harassment / self-harm incitement", 0.90),
        (re.compile(r"\b(worthless|disgusting loser|pathetic idiot|ugly freak)\b", re.IGNORECASE), "Targeted derogatory harassment", 0.60),
    ],
}


def scan_lexicon(text: str) -> list[LexiconHit]:
    """Scan text for rule-based suspicious patterns across threat, phishing, and abuse."""
    if not text:
        return []

    hits: list[LexiconHit] = []
    for category, pattern_list in _PATTERNS.items():
        for pattern, desc, weight in pattern_list:
            for match in pattern.finditer(text):
                hits.append(
                    LexiconHit(
                        category=category,
                        term=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        description=desc,
                        weight=weight,
                    )
                )

    # Sort hits chronologically by start position
    hits.sort(key=lambda h: (h.start, -h.weight))
    return hits
