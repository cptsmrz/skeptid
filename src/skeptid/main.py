"""FastAPI application factory for SKEPTID."""

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from skeptid.api.routes import router
from skeptid.api.security import SecurityHeadersMiddleware
from skeptid.core.config import SkeptidConfig, load_config
from skeptid.core.orchestrator import Orchestrator


def create_app(config: SkeptidConfig | None = None) -> FastAPI:
    """Create and configure the SKEPTID FastAPI instance."""
    app_config = config or load_config()

    app = FastAPI(
        title="SKEPTID",
        description="Multi-modal content-trust platform API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # Initialize shared orchestrator in application state
    app.state.config = app_config
    app.state.orchestrator = Orchestrator(config=app_config)

    # Attach defensive security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # Restrict CORS to self / localhost origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include core API routes
    app.include_router(router)

    # Mount static assets if web directory exists
    web_dir = Path("web")
    if web_dir.exists() and web_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    # Global unhandled exception handler to prevent leaking internal tracebacks
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error occurred. Please try again later."},
        )

    return app


# Default app instance for ASGI servers (e.g. uvicorn skeptid.main:app)
app = create_app()
