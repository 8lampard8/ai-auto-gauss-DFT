"""Persistent user settings (settings.json, mode 0600).

Stores AI provider configs (with API keys), external tool paths
(Gaussian / Multiwfn / VMD) and SSH submit profiles. Keys are masked
before being returned to the frontend; an update that submits a masked
key preserves the previously-stored secret.
"""
from __future__ import annotations

import json
import os
from typing import Any

from .config import DEFAULT_SETTINGS, SETTINGS_PATH
from .security import mask_key

SECRET_FIELDS = {"api_key", "password", "passphrase"}


def load() -> dict:
    """Load settings merged over DEFAULT_SETTINGS."""
    data: dict = {}
    if SETTINGS_PATH.exists():
        try:
            raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data = raw
        except Exception:
            data = {}
    merged = {**DEFAULT_SETTINGS, **data}
    merged.setdefault("providers", [])
    merged.setdefault("ssh_profiles", [])
    return merged


def save(data: dict) -> dict:
    """Persist settings (mode 0600) and return the merged view."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULT_SETTINGS, **data}
    merged.setdefault("providers", [])
    merged.setdefault("ssh_profiles", [])
    SETTINGS_PATH.write_text(
        json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass
    return merged


def _mask_secrets(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_mask_secrets(x) for x in obj]
    if isinstance(obj, dict):
        return {
            k: (mask_key(v) if k in SECRET_FIELDS and isinstance(v, str) else _mask_secrets(v))
            for k, v in obj.items()
        }
    return obj


def public_view() -> dict:
    """Settings safe to return to the frontend (secrets masked)."""
    s = load()
    return {
        "gaussian_path": s.get("gaussian_path", ""),
        "multiwfn_path": s.get("multiwfn_path", ""),
        "vmd_path": s.get("vmd_path", ""),
        "active_provider_id": s.get("active_provider_id", "mock"),
        "active_model": s.get("active_model", ""),
        "providers": _mask_secrets(s.get("providers", [])),
        "ssh_profiles": _mask_secrets(s.get("ssh_profiles", [])),
    }


def merge_provider_secret(existing: list[dict], incoming: dict) -> dict:
    """If ``incoming`` carries a masked/empty secret, restore the stored one."""
    out = dict(incoming)
    for field in SECRET_FIELDS:
        val = out.get(field, "")
        if not val or "*" in val:
            prev = next(
                (p.get(field, "") for p in existing if p.get("id") == incoming.get("id")),
                "",
            )
            out[field] = prev
    return out
