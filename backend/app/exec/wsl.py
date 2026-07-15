"""WSL path helpers for invoking Windows tools from the Linux backend.

The backend runs in WSL2; users may configure Windows-side Gaussian,
Multiwfn and VMD (e.g. ``D:\\gauss\\G09W\\g09w.exe``). These helpers
translate between Windows and Linux (``/mnt/<drive>/...``) path forms so the
backend can stage files and invoke the Windows executables via WSL interop.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

CMD_EXE = "/mnt/c/Windows/System32/cmd.exe"


def is_windows_path(p: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", p)) or p.lower().endswith(".exe")


def on_wsl() -> bool:
    return sys.platform == "linux" and Path("/mnt/c").exists()


def to_linux_path(p: str) -> str:
    """Windows path -> /mnt/<drive>/... ; pass through if already Linux."""
    if not is_windows_path(p):
        return p
    try:
        r = subprocess.run(["wslpath", "-u", p], capture_output=True,
                           text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    s = p.replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)", s)
    return f"/mnt/{m.group(1).lower()}/{m.group(2)}" if m else p


def to_windows_path(p: str) -> str:
    """/mnt/d/... (or Windows) path -> Windows form D:\\..."""
    try:
        r = subprocess.run(["wslpath", "-w", p], capture_output=True,
                           text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    m = re.match(r"^/mnt/([a-z])/(.*)", p)
    if m:
        return m.group(1).upper() + ":\\" + m.group(2).replace("/", "\\")
    return p


def exe_linux_path(tool_path: str, candidates: list[str]) -> str:
    """Resolve a tool to its Linux /mnt executable path.

    If ``tool_path`` is a directory, look for one of ``candidates`` inside it
    (e.g. ``Multiwfn.exe``). Otherwise translate the path to /mnt form.
    """
    linux = to_linux_path(tool_path)
    p = Path(linux)
    if p.is_dir():
        for name in candidates:
            cand = p / name
            if cand.exists():
                return str(cand)
    return linux


def tool_dir(tool_path: str) -> Path:
    """The install directory of a tool (parent if given an exe, itself if a dir)."""
    linux = to_linux_path(tool_path)
    p = Path(linux)
    return p.parent if p.is_file() else p
