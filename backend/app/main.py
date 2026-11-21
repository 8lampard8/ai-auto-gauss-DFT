"""FastAPI application entrypoint.

In development the backend runs on :8000 and the Vite dev server on :5173
(with a proxy for /api). In production the built frontend is served from
``frontend/dist`` at ``/``.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import FRONTEND_DIST
from .exec.local_runner import reconcile_orphaned_jobs
from .routers import chat, descriptors, gjf, jobs, models, molecules, system, visualize


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    try:
        reconcile_orphaned_jobs()
    except Exception:
        pass
    yield


app = FastAPI(title="ai-auto-gauss-DFT", version=__version__, lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api"
for r in (system, models, chat, molecules, descriptors, gjf, jobs, visualize):
    app.include_router(r.router, prefix=API_PREFIX)


# Serve the built SPA in production. Registered last so /api/* wins.
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    @app.get("/")
    def root() -> dict:
        """Fallback when no built frontend is present (dev mode)."""
        return {
            "app": "ai-auto-gauss-DFT",
            "version": __version__,
            "docs": "/docs",
            "api": "/api/health",
        }
