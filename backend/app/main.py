"""HealthBridge API (BRD §10) — FastAPI application entry point.

Step 1 scaffold: app construction, CORS for the Next.js frontend, and a health
probe. Auth, persistence, upload and processing routes are layered on in later
steps; this module's job is just to boot a documented, CORS-enabled server.

Run (from backend/):
    uvicorn app.main:app --reload
Interactive docs: http://localhost:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import router as auth_router
from app.config import get_settings
from app.db import init_db
from app.process import router as process_router
from app.results import router as results_router
from app.upload import router as upload_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the SQLite schema on startup."""
    init_db()
    yield


app = FastAPI(
    title="HealthBridge Group Health Index API",
    description="Privacy-preserving portal: upload, de-identify, score, group (k>=20).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(process_router)
app.include_router(results_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe + a heads-up when insecure dev secrets are still in use."""
    return {
        "status": "ok",
        "service": "healthbridge-api",
        "version": app.version,
        "using_dev_secrets": settings.is_dev_secret,
    }
