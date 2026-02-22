"""FastAPI application entry point for Prospect Intelligence platform."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.web.routes import campaigns, enrichment, accounts, contacts, exports, jobs

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Prospect Intelligence",
    description="Unified B2B prospect research and lead generation platform",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(campaigns.router, prefix="/api/campaigns")
app.include_router(enrichment.router, prefix="/api/enrichment")
app.include_router(accounts.router, prefix="/api/accounts")
app.include_router(contacts.router, prefix="/api/contacts")
app.include_router(exports.router, prefix="/api/exports")
app.include_router(jobs.router, prefix="/api/jobs")


@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/api/status")
def api_status():
    """Return which API keys are configured."""
    return {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "serper": bool(os.environ.get("SERPER_API_KEY")),
        "hunter": bool(os.environ.get("HUNTER_API_KEY")),
        "github": bool(os.environ.get("GITHUB_TOKEN")),
    }


# Serve React frontend if built
_FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        """Serve the React SPA for all non-API routes."""
        return FileResponse(str(_FRONTEND_DIST / "index.html"))


def start():
    """Start the FastAPI server (used by `leadgen serve` and `prospect` CLI)."""
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    reload = os.environ.get("ENV", "development") == "development"
    uvicorn.run("src.web.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start()
