"""Application configuration and well-known paths.

All long-lived state lives under ``DATA_DIR`` (the repo ``data/`` folder):
uploads, job work directories, rendered plots, the SQLite ledger and the
user settings file (API keys, external tool paths, SSH profiles).
"""
from __future__ import annotations

import os
from pathlib import Path

# Repo root: backend/app/config.py -> parents[2] == ai-auto-gauss-DFT/
ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = Path(os.environ.get("AAGD_DATA_DIR", ROOT / "data"))
UPLOADS_DIR = DATA_DIR / "uploads"
JOBS_DIR = DATA_DIR / "jobs"
PLOTS_DIR = DATA_DIR / "plots"
DB_PATH = DATA_DIR / "app.db"
SETTINGS_PATH = DATA_DIR / "settings.json"

# Frontend build served by FastAPI in production.
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Defaults for external tool paths / AI provider selection. These are merged
# with whatever the user persists in settings.json.
DEFAULT_SETTINGS: dict = {
    "gaussian_path": "",          # e.g. /opt/g16/g16  (local Gaussian executable)
    "multiwfn_path": "",          # e.g. /opt/Multiwfn/Multiwfn
    "vmd_path": "/home/heyihao/vmd/vmd",
    "active_provider_id": "mock", # provider id used for chat when none pinned
    "active_model": "",           # model id within the active provider
    "providers": [],              # list of provider configs (see ai.provider)
    "ssh_profiles": [],           # list of SSH submit profiles
}

# Resource recommendation defaults for local execution.
LOCAL_RESERVE_CORES = 2          # leave this many physical cores free
LOCAL_MEM_FRACTION = 0.70        # cap %mem at this fraction of total RAM


def ensure_dirs() -> None:
    """Create the data sub-tree if missing (idempotent)."""
    for d in (DATA_DIR, UPLOADS_DIR, JOBS_DIR, PLOTS_DIR):
        d.mkdir(parents=True, exist_ok=True)


ensure_dirs()
