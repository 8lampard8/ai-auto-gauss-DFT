"""Multiwfn driver — Linux native or Windows via WSL interop.

Multiwfn is menu-driven; the ``input_lines`` are fed to stdin after the
.fchk path. On WSL2 the Windows ``Multiwfn.exe`` is invoked via /mnt interop,
and the .fchk path passed on stdin is given in Windows form (``D:\\...``) so
the Windows process can resolve it. Cube files are written to ``work_dir``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .wsl import is_windows_path, on_wsl, exe_linux_path, to_windows_path


def run(
    multiwfn_path: str,
    fchk_path: Path,
    work_dir: Path,
    input_lines: list[str],
    timeout: int = 900,
) -> str:
    windows = is_windows_path(multiwfn_path) and on_wsl()
    exe = (
        exe_linux_path(multiwfn_path, ["Multiwfn.exe", "Multiwfn"])
        if windows else multiwfn_path
    )
    # First stdin line = the .fch path. Windows Multiwfn needs a Windows path.
    fchk_arg = to_windows_path(str(fchk_path)) if windows else str(fchk_path)
    cmd_text = "\n".join([fchk_arg, *input_lines]) + "\n"
    try:
        proc = subprocess.run(
            [exe], input=cmd_text, cwd=str(work_dir),
            capture_output=True, text=True, timeout=timeout,
        )
        return (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return f"[error] Multiwfn 可执行文件未找到:{exe}"
    except subprocess.TimeoutExpired:
        return f"[error] Multiwfn 运行超时(>{timeout}s)"
    except Exception as e:  # pragma: no cover
        return f"[error] {type(e).__name__}: {e}"
