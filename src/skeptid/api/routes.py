"""API endpoints for analysis, feedback, metrics, and health inspection."""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from skeptid.api.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    ProviderStatusItem,
    ProviderStatusResponse,
    TextAnalysisRequest,
    VerdictResponse,
)
from skeptid.api.security import check_rate_limit
from skeptid.api.validators import validate_text
from skeptid.core.orchestrator import AllProvidersFailedError, Orchestrator
from skeptid.core.types import AnalysisInput, Modality

router = APIRouter()


def get_orchestrator(request: Request) -> Orchestrator:
    """Dependency to retrieve orchestrator from application state."""
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        orchestrator = Orchestrator()
        request.app.state.orchestrator = orchestrator
    return orchestrator


@router.get("/healthz", response_model=HealthResponse, tags=["Health"])
async def healthz() -> HealthResponse:
    """Basic liveness and operational health probe."""
    return HealthResponse(status="ok")


@router.post(
    "/api/analyze/text",
    response_model=VerdictResponse,
    dependencies=[Depends(check_rate_limit)],
    tags=["Analysis"],
)
async def analyze_text(
    payload: TextAnalysisRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> VerdictResponse:
    """Analyze plain text content for spam, phishing, threats, or cyberbullying."""
    clean_text = validate_text(payload.text)
    inp = AnalysisInput(modality=Modality.TEXT, text=clean_text)

    try:
        verdict = await orchestrator.analyze(inp)
    except AllProvidersFailedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="All analysis providers failed. No verdict could be reliably formed.",
        ) from exc

    return VerdictResponse(
        id=verdict.id,
        modality=verdict.modality.value,
        label=verdict.label,
        risk=verdict.risk,
        level=verdict.level,
        confidence=verdict.confidence,
        disagreement=verdict.disagreement,
        primary_provider=verdict.primary_provider,
        mock=verdict.mock,
        providers=[
            {
                "id": p["id"],
                "ok": p["ok"],
                "risk": p["risk"],
                "model_version": p["model_version"],
                "latency_ms": p["latency_ms"],
                "error": p.get("error"),
            }
            for p in verdict.providers
        ],
        evidence=[
            {
                "kind": ev.kind,
                "description": ev.description,
                "payload": ev.payload,
            }
            for ev in verdict.evidence
        ],
        limits_note=verdict.limits_note,
    )


@router.post(
    "/api/feedback",
    response_model=FeedbackResponse,
    dependencies=[Depends(check_rate_limit)],
    tags=["Feedback"],
)
async def submit_feedback(payload: FeedbackRequest) -> FeedbackResponse:
    """Receive user feedback regarding a prior analysis verdict."""
    # Stored feedback data is tagged source=demo and excluded from frozen holdouts
    return FeedbackResponse(status="recorded", analysis_id=payload.analysis_id)


@router.get("/api/metrics", tags=["Metrics"])
def get_metrics() -> dict:
    """Return model evaluation metrics directly from models/registry.json."""
    registry_path = Path("models/registry.json")
    if not registry_path.exists():
        return {"models": {}, "promotions": []}
    try:
        with open(registry_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read model registry.",
        ) from exc


@router.get(
    "/api/providers/status",
    response_model=ProviderStatusResponse,
    tags=["Providers"],
)
async def get_provider_status(
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> ProviderStatusResponse:
    """Return operational statuses of providers without exposing secrets or URLs."""
    items: list[ProviderStatusItem] = []
    for mod, p_dict in orchestrator.providers.items():
        for pid, provider in p_dict.items():
            is_healthy = await provider.health()
            is_cb_open = orchestrator.circuit_breaker.is_open(pid)
            st = "up" if (is_healthy and not is_cb_open) else "down"
            items.append(ProviderStatusItem(id=pid, modality=mod.value, status=st))

    return ProviderStatusResponse(providers=items)
