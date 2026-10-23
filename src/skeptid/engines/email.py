"""Email analysis engine.

Parses .eml messages using standard library email, analyzes body text via the
orchestrator, runs URL and header forensics, inspects attachments (up to 3, max 10MB),
and computes in-lane fusion per SPEC sections 6.2 and 7.
"""

import email
import io
import logging
import re
import unicodedata
from email import policy
from email.message import EmailMessage
from typing import Any

from PIL import Image, UnidentifiedImageError

from skeptid.core.fusion import (
    classify_risk_level,
    fuse_email_components,
)
from skeptid.core.orchestrator import Orchestrator
from skeptid.core.types import (
    AnalysisInput,
    Evidence,
    Modality,
    Verdict,
)
from skeptid.forensics.headers import analyze_headers
from skeptid.forensics.urls import analyze_urls
from skeptid.providers.own_image import OwnImageProvider

MAX_ATTACHMENTS = 3
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

DANGEROUS_EXTENSIONS = {
    ".exe",
    ".scr",
    ".vbs",
    ".js",
    ".bat",
    ".cmd",
    ".iso",
    ".hta",
    ".jar",
    ".ps1",
    ".wsf",
}

logger = logging.getLogger(__name__)


class EmailEngine:
    """Intake and forensic analysis engine for email messages (.eml)."""

    def __init__(self, orchestrator: Orchestrator) -> None:
        self.orchestrator = orchestrator
        self.own_image_provider = OwnImageProvider()

    def parse_eml(
        self, raw_bytes: bytes
    ) -> tuple[str, str | None, EmailMessage, list[dict[str, Any]]]:
        """Parse raw RFC822 bytes into plain text body, html, msg object, and attachments."""
        msg = email.message_from_bytes(raw_bytes, policy=policy.default)

        plain_text = ""
        html_text = None
        attachments: list[dict[str, Any]] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition", ""))
                content_type = part.get_content_type()

                if "attachment" in content_disposition or part.get_filename():
                    if len(attachments) < MAX_ATTACHMENTS:
                        payload = part.get_payload(decode=True) or b""
                        if len(payload) <= MAX_ATTACHMENT_SIZE_BYTES:
                            attachments.append(
                                {
                                    "filename": part.get_filename() or "attachment",
                                    "content_type": content_type,
                                    "size_bytes": len(payload),
                                    "payload": payload,
                                }
                            )
                elif content_type == "text/plain" and not plain_text:
                    payload = part.get_payload(decode=True) or b""
                    plain_text = payload.decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
                elif content_type == "text/html" and html_text is None:
                    payload = part.get_payload(decode=True) or b""
                    html_text = payload.decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
        else:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            if msg.get_content_type() == "text/html":
                html_text = payload.decode(charset, errors="replace")
                plain_text = re.sub(r"<[^>]+>", " ", html_text)
            else:
                plain_text = payload.decode(charset, errors="replace")

        if not plain_text and html_text:
            plain_text = re.sub(r"<[^>]+>", " ", html_text)

        return plain_text.strip(), html_text, msg, attachments

    async def inspect_attachments(
        self, raw_attachments: list[dict[str, Any]]
    ) -> tuple[float | None, list[Evidence], list[dict[str, Any]]]:
        """Analyze up to 3 attachments for forensic risks and dangerous payloads."""
        if not raw_attachments:
            return None, [], []

        attachment_risks: list[float] = []
        evidence: list[Evidence] = []
        attachment_summaries: list[dict[str, Any]] = []

        for att in raw_attachments[:MAX_ATTACHMENTS]:
            filename = att["filename"].lower()
            payload = att["payload"]
            content_type = att["content_type"]
            item_risk = 0.0
            flags: list[str] = []

            # 1. Dangerous extension check
            for ext in DANGEROUS_EXTENSIONS:
                if filename.endswith(ext):
                    item_risk = max(item_risk, 0.95)
                    flags.append("executable_or_script_attachment")
                    evidence.append(
                        Evidence(
                            kind="flag",
                            description=f"Dangerous executable/script attachment detected: '{att['filename']}'",
                            payload={
                                "attachment": att["filename"],
                                "indicator": "dangerous_extension",
                                "extension": ext,
                            },
                        )
                    )

            # 2. Image attachment forensic baseline
            if content_type.startswith("image/"):
                try:
                    with Image.open(io.BytesIO(payload)) as img:
                        w, h = img.size
                    img_inp = AnalysisInput(
                        modality=Modality.IMAGE,
                        raw_bytes=payload,
                        filename=att["filename"],
                        metadata={"width": w, "height": h},
                    )
                    img_res = await self.own_image_provider.analyze(img_inp)
                    if img_res.ok:
                        item_risk = max(item_risk, img_res.risk)
                        if img_res.risk >= 0.70:
                            evidence.append(
                                Evidence(
                                    kind="flag",
                                    description=f"Attachment '{att['filename']}' forensic anomaly score elevated ({img_res.risk:.2f})",
                                    payload={"attachment": att["filename"], "score": img_res.risk},
                                )
                            )
                except (UnidentifiedImageError, OSError, ValueError) as exc:
                    logger.debug(
                        "Image attachment inspection skipped for %s: %s", att["filename"], exc
                    )

            needs_review = item_risk >= 0.70
            if needs_review and "needs_review" not in flags:
                flags.append("Attachment needs review")

            attachment_risks.append(item_risk)
            attachment_summaries.append(
                {
                    "filename": att["filename"],
                    "content_type": content_type,
                    "size_bytes": att["size_bytes"],
                    "risk": round(item_risk, 4),
                    "needs_review": needs_review,
                    "flags": flags,
                }
            )

        overall_attachment_risk = max(attachment_risks) if attachment_risks else 0.0
        return round(overall_attachment_risk, 4), evidence, attachment_summaries

    async def analyze(
        self,
        raw_eml_bytes: bytes,
        filename: str | None = None,
        use_external: bool = True,
    ) -> Verdict:
        """Execute full email message analysis with in-lane fusion."""
        # 1. Parse message
        plain_text, html_text, msg, raw_attachments = self.parse_eml(raw_eml_bytes)
        clean_text = unicodedata.normalize("NFKC", (plain_text or "(empty email body)").strip())

        # 2. Dispatch body text to Orchestrator (concurrent providers)
        body_input = AnalysisInput(
            modality=Modality.TEXT,
            text=clean_text,
            filename=filename,
            use_external=use_external,
        )
        text_verdict = await self.orchestrator.analyze(body_input)
        text_risk = text_verdict.risk

        # 3. URL Forensics
        url_risk, url_evidence, _ = analyze_urls(plain_text, html_text)

        # 4. Header Forensics
        header_risk, header_evidence, _ = analyze_headers(msg)

        # 5. Attachment Forensics
        (
            attachment_risk,
            attachment_evidence,
            _attachment_summaries,
        ) = await self.inspect_attachments(raw_attachments)

        # 6. In-lane Fusion per SPEC section 7 & 6.2:
        # risk = 0.60*text + 0.15*url + 0.15*header + 0.10*attachment
        fused_risk = fuse_email_components(
            text_risk=text_risk,
            url_risk=url_risk,
            header_risk=header_risk,
            attachment_risk=attachment_risk,
        )

        # 7. Merge evidence
        combined_evidence: list[Evidence] = []
        combined_evidence.extend(text_verdict.evidence)
        combined_evidence.extend(url_evidence)
        combined_evidence.extend(header_evidence)
        combined_evidence.extend(attachment_evidence)

        # 8. Determine label
        if fused_risk >= 0.50:
            final_label = "phishing"
        elif text_verdict.label == "spam" and fused_risk >= 0.35:
            final_label = "spam"
        else:
            final_label = text_verdict.label if fused_risk < 0.35 else "phishing"

        level = classify_risk_level(fused_risk)

        # Re-estimate confidence with fused risk
        confidence = text_verdict.confidence

        return Verdict(
            id=text_verdict.id,
            modality=Modality.EMAIL,
            label=final_label,
            risk=fused_risk,
            level=level,
            confidence=confidence,
            disagreement=text_verdict.disagreement,
            primary_provider=text_verdict.primary_provider,
            mock=text_verdict.mock,
            providers=text_verdict.providers,
            evidence=combined_evidence,
            limits_note="Risk score with evidence, not proof. Email risk fused from body (60%), URL (15%), headers (15%), and attachments (10%).",
            validated=text_verdict.validated,
            external_used=text_verdict.external_used,
        )
