"""Security helpers.

The visualization pipeline is only allowed to write inside the configured
Multiwfn directory and VMD directory (plus the app ``data/`` tree). These
helpers enforce that boundary and reject path-escape attempts.
"""
from __future__ import annotations

from pathlib import Path

from .config import DATA_DIR, JOBS_DIR, PLOTS_DIR, UPLOADS_DIR, SETTINGS_PATH


def _resolve(p: str | Path) -> Path:
    return Path(p).expanduser().resolve()


def is_within(path: str | Path, root: str | Path) -> bool:
    """True if ``path`` resolves inside ``root``."""
    try:
        rp, rr = _resolve(path), _resolve(root)
    except Exception:
        return False
    if rp == rr:
        return True
    try:
        rp.relative_to(rr)
        return True
    except ValueError:
        return False


def assert_writable(path: str | Path, allowed_roots: list[str | Path]) -> Path:
    """Resolve ``path`` and ensure it sits inside one of ``allowed_roots``.

    Raises ``PermissionError`` otherwise. Returns the resolved path.
    """
    rp = _resolve(path)
    for root in allowed_roots:
        if is_within(rp, root):
            # Pre-create the parent so callers can write immediately.
            rp.parent.mkdir(parents=True, exist_ok=True)
            return rp
    raise PermissionError(
        f"Refusing to write outside allowed directories: {rp} "
        f"(allowed roots: {allowed_roots})"
    )


def app_data_roots() -> list[Path]:
    """Roots the app itself may always write to."""
    return [DATA_DIR, UPLOADS_DIR, JOBS_DIR, PLOTS_DIR, SETTINGS_PATH.parent]


def mask_key(key: str | None) -> str:
    """Return a masked form of a secret for display/logging."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]
