"""VMD driver — run a .vmd script headless and convert the render to PNG.

Linux native or Windows ``vmd.exe`` via WSL interop. The script is written
into ``vmd_dir`` and invoked with cwd there (so relative cube paths resolve);
TachyonInternal writes a .tga which Pillow converts to PNG.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .wsl import is_windows_path, on_wsl, exe_linux_path


def render(
    vmd_path: str,
    vmd_dir: Path,
    script_text: str,
    png_path: Path,
    timeout: int = 120,
) -> tuple[str, bool]:
    vmd_dir = Path(vmd_dir)
    script = vmd_dir / "render.vmd"
    script.write_text(script_text, encoding="utf-8")

    windows = is_windows_path(vmd_path) and on_wsl()
    exe = (
        exe_linux_path(vmd_path, ["vmd.exe", "vmd"])
        if windows else vmd_path
    )
    try:
        proc = subprocess.run(
            [exe, "-dispdev", "text", "-e", "render.vmd"],
            cwd=str(vmd_dir), capture_output=True, text=True, timeout=timeout,
        )
        log = (proc.stdout or "") + (proc.stderr or "")
    except FileNotFoundError:
        return f"[error] VMD 可执行文件未找到:{exe}", False
    except subprocess.TimeoutExpired:
        return f"[error] VMD 运行超时(>{timeout}s)", False
    except Exception as e:  # pragma: no cover
        return f"[error] {type(e).__name__}: {e}", False

    converted = False
    for tga in vmd_dir.glob("*.tga"):
        try:
            from PIL import Image

            Image.open(tga).save(png_path)
            converted = True
        except Exception as e:
            log += f"\n[warn] 转换 {tga.name} -> PNG 失败:{e}"
    return log, converted
