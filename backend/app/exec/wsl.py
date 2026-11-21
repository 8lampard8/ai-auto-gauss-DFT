"""Cross-platform / WSL path helpers for invoking external chemistry tools.

Supports three runtime environments transparently:
1. **WSL2 (Linux backend -> Windows tools)**: translates ``D:\\...`` to
   ``/mnt/d/...`` for file staging and passes Windows-form paths to Windows
   executables invoked via WSL interop.
2. **Native Windows**: keeps Windows paths as-is.
3. **Native Linux / macOS**: keeps POSIX paths as-is.
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


def on_windows() -> bool:
    return sys.platform == "win32"


def to_linux_path(p: str) -> str:
    """Windows path -> /mnt/<drive>/... on WSL; unchanged on native Windows/Linux."""
    if not is_windows_path(p) or not on_wsl():
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
    """/mnt/d/... -> D:\\... on WSL; unchanged on native Windows."""
    if on_windows():
        return str(Path(p))
    if not on_wsl():
        return p
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
    """Resolve a tool path (file or directory) to a host-runnable executable."""
    resolved = to_linux_path(tool_path)
    p = Path(resolved)
    if p.is_dir():
        for name in candidates:
            cand = p / name
            if cand.exists():
                return str(cand)
    return resolved


def tool_dir(tool_path: str) -> Path:
    """The install directory of a tool (parent if given an exe, itself if a dir)."""
    resolved = to_linux_path(tool_path)
    p = Path(resolved)
    if p.is_file() or p.suffix.lower() in (".exe", ".bat", ".cmd", ".sh"):
        return p.parent
    return p
