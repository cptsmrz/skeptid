"""Pydantic schemas for SKEPTID API endpoints."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class MessageAnalysisRequest(BaseModel):
    """Request payload for text message analysis."""

    text: str = Field(..., max_length=20000, description="Raw text to evaluate (max 20,000 chars)")
    use_external: bool = Field(True, description="Whether to invoke external provider")


TextAnalysisRequest = MessageAnalysisRequest


class EvidenceSchema(BaseModel):
    """Forensic evidence entry."""

    kind: Literal[
        "span", "heatmap", "frame_score", "metric", "flag", "spectrum", "hop_trace", "hex_entropy"
    ]
    description: str
    payload: dict[str, Any]


class ProviderSummarySchema(BaseModel):
    """Summary of provider performance and result."""

    id: str
    ok: bool
    risk: float
    model_version: str
    latency_ms: int
    error: str | None = None
    validated: bool | None = None


class VerdictResponse(BaseModel):
    """Unified verdict response format."""

    id: str
    modality: str
    label: str
    risk: float
    level: str
    confidence: float
    disagreement: bool
    primary_provider: str
    mock: bool
    providers: list[ProviderSummarySchema]
    evidence: list[EvidenceSchema]
    limits_note: str = "Risk score with evidence, not proof."
    validated: bool = True
    external_used: bool = False


class FeedbackRequest(BaseModel):
    """User feedback on analysis verdict.

    If share_example=True and text is provided, the message text is stored
    in a separate feedback_samples table for retrain use (SPEC §9).
    Media is never stored — this applies to text modality only.
    """

    analysis_id: str
    correct: bool
    true_label: str | None = None
    share_example: bool = Field(
        False,
        description="If true, the text of this message will be stored to improve the model. "
        "By ticking this option you consent to your message text being used for training.",
    )
    text: str | None = Field(
        None,
        max_length=20000,
        description="The message text to share. Only stored when share_example=True.",
    )


class FeedbackResponse(BaseModel):
    """Feedback submission acknowledgment."""

    status: str = "recorded"
    analysis_id: str


class ProviderStatusItem(BaseModel):
    """Public operational health of a provider."""

    id: str
    modality: str
    status: Literal["up", "down"]


class ProviderStatusResponse(BaseModel):
    """Response containing list of provider operational statuses."""

    providers: list[ProviderStatusItem]


class HealthResponse(BaseModel):
    """Health check status."""

    status: str = "ok"
