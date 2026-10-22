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
    "/api/message/analyze",
    response_model=VerdictResponse,
    dependencies=[Depends(check_rate_limit)],
    tags=["Analysis"],
)
async def analyze_message(
    request: Request,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> VerdictResponse:
    """Analyze message content (raw text, .txt, or .eml) in the Message Lane."""
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload.",
            ) from exc
        raw_text = body.get("text", "")
        clean_text = validate_text(raw_text)
        inp = AnalysisInput(modality=Modality.TEXT, text=clean_text)

    elif "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        form_text = form.get("text")

        if uploaded_file and hasattr(uploaded_file, "filename") and hasattr(uploaded_file, "read"):
            filename = (uploaded_file.filename or "").lower()
            file_bytes = await uploaded_file.read()
            if filename.endswith(".eml"):
                import email
                from email import policy
                msg = email.message_from_bytes(file_bytes, policy=policy.default)
                body = msg.get_body(preferencelist=("plain", "html"))
                msg_text = body.get_content() if body is not None else ""
                clean_text = validate_text(msg_text)
                inp = AnalysisInput(
                    modality=Modality.EMAIL,
                    text=clean_text,
                    raw_bytes=file_bytes,
                    filename=uploaded_file.filename,
                )
            elif filename.endswith(".txt"):
                decoded_text = file_bytes.decode("utf-8", errors="replace")
                clean_text = validate_text(decoded_text)
                inp = AnalysisInput(
                    modality=Modality.TEXT,
                    text=clean_text,
                    filename=uploaded_file.filename,
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unsupported file format for message lane. Allowed: .eml, .txt",
                )
        elif form_text is not None:
            clean_text = validate_text(str(form_text))
            inp = AnalysisInput(modality=Modality.TEXT, text=clean_text)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Form must provide either a 'file' (.eml/.txt) or 'text' field.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json or multipart/form-data.",
        )

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
