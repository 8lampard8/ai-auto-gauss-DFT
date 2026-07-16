"""Local Gaussian runner.

Handles two execution modes:

1. **Linux Gaussian** (g16 on PATH or an absolute Unix path): run the
   executable directly via subprocess.
2. **Windows Gaussian on WSL2** (e.g. G09W ``D:\\gauss\\G09W\\g09w.exe``):
   the backend itself runs in Linux, so we translate the path to ``/mnt/d/...``,
   stage the gjf on the Windows drive, and invoke ``g09.exe`` headless through
   ``cmd.exe`` (WSL interop) with ``GAUSS_EXEDIR`` / ``GAUSS_SCRDIR`` set.
   ``g09w.exe`` (the GUI launcher) is auto-substituted with ``g09.exe``.

A daemon thread waits for completion, copies job.log / .fchk back into the
WSL job directory, and marks the job succeeded if "Normal termination"
appears in the log.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from ..chemistry.gjf_writer import generate_gjf
from ..config import JOBS_DIR
from ..jobs_store import update as update_job

_CMD_EXE = "/mnt/c/Windows/System32/cmd.exe"


def _sanitize_mem(mem: str) -> str:
    """Gaussian %mem needs an integer + unit (GB/MB/MW/KW). A decimal like
    '10.8GB' is a syntax error; convert to an integer MB form."""
    if not mem:
        return mem
    m = re.match(r"^\s*([\d.]+)\s*([A-Za-z]+)\s*$", mem)
    if not m:
        return mem
    val = float(m.group(1))
    unit = m.group(2).upper()
    if val == int(val):
        return f"{int(val)}{m.group(2)}"          # 10.0GB -> 10GB
    mult = {"GB": 1024, "MB": 1, "MW": 8}
    if unit in mult:
        return f"{int(round(val * mult[unit]))}MB"
    return mem


def _mem_to_mb(mem: str) -> int | None:
    m = re.match(r"^\s*(\d+)\s*MB\s*$", mem)
    return int(m.group(1)) if m else None


def _cap_mem(mem: str, max_mb: int) -> str:
    """If mem (in MB form) exceeds max_mb, clamp it down."""
    mb = _mem_to_mb(mem)
    if mb is not None and mb > max_mb:
        return f"{max_mb}MB"
    return mem


def _is_g09w(gaussian_path: str) -> bool:
    """Gaussian 09 for Windows is 32-bit (IA32W) and can't address >~2GB."""
    return "g09w" in gaussian_path.lower()


def _is_link0_crash(text: str) -> bool:
    """G09W exits right after the SMP line, before parsing the route section.
    Signature: 'Will use up to N processors' present, but no '#' route line
    and no 'Error termination' after it."""
    t = text or ""
    smp = re.search(r"Will use up to\s+\d+\s+processors", t)
    if not smp:
        return False
    after = t[smp.end():]
    return "#" not in after and "Error termination" not in after


def _extract_gaussian_error(text: str, rc: int) -> str:
    """Pull a concise, actionable reason out of a Gaussian log on failure."""
    t = text or ""
    if _is_link0_crash(t):
        return (f"exit={rc};G09W 在解析 route 前退出(通常 %mem 过大或 "
                "%nprocshared 超出许可核数)。建议 %mem≤1000MB、%nprocshared=1 重试。")
    for pat, hint in [
        (r"Insufficient memory|Out of memory|malloc failed|not enough memory",
         "内存不足:32 位 G09W 内存有限,请换更小基组、减小 %mem 或减小体系。"),
        (r"NTrErr|too many (basis functions|primitives)|maximum number of primitive",
         "基函数过多,超出 32 位 G09W 上限:请换小基组(如 6-31G*)或减少原子。"),
        (r"QPErr|A syntax error was detected in the input",
         "输入语法错误:检查 route 关键字、电荷多重度行、坐标格式。"),
        (r"wsystem|No executable for file|No such file.*\.exe",
         "Gaussian 子程序(link)启动失败:检查 GAUSS_EXEDIR 与 G09W 安装完整性。"),
    ]:
        if re.search(pat, t, re.I):
            return f"exit={rc};{hint}"
    m = re.search(r"forrtl: severe \((\d+)\)", t)
    if m:
        return (f"exit={rc};Fortran 运行时错误(severe {m.group(1)}),"
                "常见于内存/磁盘不足或体系过大。")
    m = re.search(r"Error termination via Lnk\w+ in (\S+\.exe)", t)
    if m:
        link = m.group(1)
        idx = t.rfind("Error termination")
        ctx = [ln.strip() for ln in t[max(0, idx - 200):idx].splitlines() if ln.strip()]
        tail = " | ".join(ctx[-3:])[:160]
        return f"exit={rc};Gaussian 在 {link} 失败{(': ' + tail) if tail else ''}。"
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    tail = lines[-1][:120] if lines else "(空日志)"
    return f"exit={rc};未见 Normal termination。日志末尾:{tail}"


_BASIS_WEIGHTS = {
    "def2-svp": 15, "6-31g(d)": 15, "6-31g*": 15, "6-31g(d,p)": 16, "6-31g**": 16,
    "6-311g(d,p)": 25, "6-311g**": 25, "def2-tzvp": 30, "ma-def2-tzvp": 32,
    "def2-tzvpp": 40, "cc-pvtz": 40, "aug-cc-pvtz": 55, "def2-qzvpp": 60,
}


def _estimate_basis_functions(n_atoms: int, basis: str) -> int:
    """Rough basis-function count for a pre-flight G09W feasibility check."""
    return n_atoms * _BASIS_WEIGHTS.get((basis or "").lower(), 25)


# ---------------------------------------------------------------------------
# path helpers (WSL <-> Windows)
# ---------------------------------------------------------------------------
def _is_windows_gaussian(path: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", path)) or path.lower().endswith(".exe")


def _win_to_linux(win_path: str) -> str:
    """D:\\gauss\\G09W\\g09.exe -> /mnt/d/gauss/G09W/g09.exe"""
    p = win_path.replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/(.*)", p)
    if m:
        return f"/mnt/{m.group(1).lower()}/{m.group(2)}"
    return win_path


def _wslpath(path: str, to_win: bool) -> str:
    flag = "-w" if to_win else "-u"
    try:
        r = subprocess.run(["wslpath", flag, path], capture_output=True,
                           text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return path


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def submit_local(job_id: str, molecule, spec, gaussian_path: str,
                 nproc: int, mem: str, gjf_text: str | None = None) -> None:
    work = JOBS_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)
    extra_note = ""

    if gjf_text:
        # User-edited gjf: use it verbatim (no regeneration, no G09W caps).
        gjf = gjf_text
        m_np = re.search(r"%nprocshared\s*=\s*(\d+)", gjf, re.I)
        m_mem = re.search(r"%mem\s*=\s*(\S+)", gjf, re.I)
        rec_nproc = int(m_np.group(1)) if m_np else nproc
        rec_mem = m_mem.group(1) if m_mem else mem
    else:
        spec.nproc = nproc
        spec.memory = _sanitize_mem(mem)

        # G09W is 32-bit (IA32W) with a 4-core license: clamp %mem (<=~1.5GB, else
        # the 32-bit process can't address it) and %nprocshared (<=4, else exit=9
        # right after the link-0 cards with no error in the log).
        if _is_windows_gaussian(gaussian_path) and _is_g09w(gaussian_path):
            capped_mem = _cap_mem(spec.memory, 1500)
            if capped_mem != spec.memory:
                extra_note += f"G09W 为 32 位,已将 %mem 由 {spec.memory} 限制为 {capped_mem};"
                spec.memory = capped_mem
            if spec.nproc and spec.nproc > 4:
                extra_note += f"G09W 许可限 4 核,已将 %nprocshared 由 {spec.nproc} 降为 4;"
                spec.nproc = 4
            est = _estimate_basis_functions(len(molecule.atoms), spec.basis)
            if est > 400:
                extra_note += (f" 估算基函数约 {est},超出 32 位 G09W 常规能力(>~400),"
                               "建议换 6-31G* 或更小基组,否则易 exit=9/内存超限。")
        try:
            gjf = generate_gjf(molecule, spec)
        except ValueError as e:
            update_job(job_id, status="failed", error=str(e))
            return
        rec_nproc = nproc
        rec_mem = spec.memory

    gjf_path = work / "job.gjf"
    gjf_path.write_text(gjf, encoding="utf-8")
    update_job(job_id, gjf_path=str(gjf_path), work_dir=str(work),
               nproc=rec_nproc, mem=rec_mem)

    if not gaussian_path:
        update_job(
            job_id,
            status="queued",
            message="未配置本地 Gaussian 路径;已生成 gjf,可下载后手动执行。",
        )
        return

    if _is_windows_gaussian(gaussian_path) and sys.platform == "linux":
        _submit_windows(job_id, work, gjf_path, gaussian_path, extra_note)
    else:
        _submit_linux(job_id, work, gjf_path, gaussian_path)


# ---------------------------------------------------------------------------
# Linux Gaussian
# ---------------------------------------------------------------------------
def _submit_linux(job_id: str, work: Path, gjf_path: Path, gaussian_path: str) -> None:
    log_path = work / "job.log"
    try:
        log_fp = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            [gaussian_path, str(gjf_path)],
            cwd=str(work),
            stdout=log_fp,
            stderr=subprocess.STDOUT,
        )
    except Exception as e:
        update_job(job_id, status="failed",
                   error=f"启动 Gaussian 失败:{e}", log_path=str(log_path))
        return

    update_job(job_id, status="running", log_path=str(log_path),
               remote_pid=str(proc.pid))

    def watch() -> None:
        rc = proc.wait()
        try:
            log_fp.close()
        except Exception:
            pass
        text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        term = "Normal termination" in text
        if term:
            fields = {"status": "succeeded", "error": "",
                      "message": "Normal termination of Gaussian 16."}
            fchk = _linux_formchk(work, gaussian_path)
            if fchk:
                fields["fchk_path"] = str(fchk)
            update_job(job_id, **fields)
        else:
            update_job(job_id, status="failed",
                       error=_extract_gaussian_error(text, rc))

    threading.Thread(target=watch, daemon=True).start()


def _linux_formchk(work: Path, gaussian_path: str) -> Path | None:
    """Best-effort formchk on Linux after a successful run."""
    formchk_exe = Path(gaussian_path).resolve().parent / "formchk"
    chk = work / "job.chk"
    fchk = work / "job.fchk"
    if not chk.exists():
        return None
    try:
        subprocess.run([str(formchk_exe), str(chk), str(fchk)],
                       cwd=str(work), capture_output=True, timeout=180)
    except Exception:
        return None
    return fchk if fchk.exists() else None


# ---------------------------------------------------------------------------
# Windows Gaussian (G09W) via WSL interop
# ---------------------------------------------------------------------------
def _run_g09w(win_work: Path, exe_win: str, exedir_win: str,
              win_work_win: str) -> tuple[int, str]:
    """Run one g09.exe pass; return (exit_code, log_text)."""
    cmd = (
        f"set GAUSS_EXEDIR={exedir_win}&& "
        f"set GAUSS_SCRDIR={win_work_win}&& "
        f"{exe_win} job.gjf job.log"
    )
    try:
        proc = subprocess.Popen([_CMD_EXE, "/c", cmd], cwd=str(win_work))
        rc = proc.wait()
    except Exception as e:
        return -1, f"启动失败:{e}"
    win_log = win_work / "job.log"
    text = win_log.read_text(encoding="utf-8", errors="ignore") if win_log.exists() else ""
    return rc, text


def _patch_gjf_resources(win_work: Path, mem: str, nproc: int) -> None:
    """Rewrite the %mem / %nprocshared lines in the staged gjf (for retries)."""
    p = win_work / "job.gjf"
    g = p.read_text(encoding="utf-8")
    g = re.sub(r"%mem=.*", f"%mem={mem}", g)
    g = re.sub(r"%nprocshared=.*", f"%nprocshared={nproc}", g)
    p.write_text(g, encoding="utf-8")


def _submit_windows(job_id: str, work: Path, gjf_path: Path,
                    gaussian_path: str, extra_note: str = "") -> None:
    if not Path(_CMD_EXE).exists():
        update_job(job_id, status="failed",
                   error="当前非 WSL2 环境,无法调用 Windows 版 Gaussian。"
                         "请在 Linux 上安装 Gaussian,或改用 SSH 提交。")
        return

    # g09w.exe is the GUI launcher -> use g09.exe (command-line) instead.
    norm = gaussian_path.replace("/", "\\")
    parts = norm.split("\\")
    basename = parts[-1]
    dirname_win = "\\".join(parts[:-1])
    note = ""
    if basename.lower() == "g09w.exe":
        basename = "g09.exe"
        note = "检测到 g09w.exe(GUI 启动器),自动改用 g09.exe(命令行)执行。"
    if extra_note:
        note = (note + " " + extra_note).strip()
    exe_win = dirname_win + "\\" + basename
    exe_linux = _win_to_linux(exe_win)
    if not os.path.exists(exe_linux):
        update_job(
            job_id, status="failed",
            error=(f"未找到 Gaussian 可执行文件:{exe_win}\n"
                   f"(WSL 路径 {exe_linux} 不存在)。请在「设置」中确认路径。"),
        )
        return

    exedir_win = dirname_win
    drive = dirname_win[0].lower()
    win_work = Path(f"/mnt/{drive}/gauss/aagd_jobs") / job_id
    win_work.mkdir(parents=True, exist_ok=True)
    shutil.copy(gjf_path, win_work / "job.gjf")
    win_work_win = _wslpath(str(win_work), to_win=True)

    update_job(job_id, status="running", is_windows=True,
               message=note + f"通过 WSL interop 调用 {exe_win}",
               work_dir=str(work),
               log_path=str(win_work / "job.log"))  # live log on the Windows side (/mnt, readable from WSL)

    def watch() -> None:
        rc, text = _run_g09w(win_work, exe_win, exedir_win, win_work_win)
        term = "Normal termination" in text

        # G09W link0-crash auto-retry: if it died before the route (mem/nproc
        # still too high for this license/machine), retry once with minimal
        # resources.
        if not term and _is_link0_crash(text):
            update_job(job_id, message="检测到 G09W link0 崩溃,以 nproc=1/mem=600MB 重试中…")
            _patch_gjf_resources(win_work, "600MB", 1)
            rc, text = _run_g09w(win_work, exe_win, exedir_win, win_work_win)
            term = "Normal termination" in text

        log_local = work / "job.log"
        if (win_work / "job.log").exists():
            shutil.copy(win_work / "job.log", log_local)

        fchk_local = work / "job.fchk"
        if term and (win_work / "job.chk").exists():
            try:
                subprocess.run(
                    [_CMD_EXE, "/c",
                     f"set GAUSS_EXEDIR={exedir_win}&& "
                     f"{exedir_win}\\formchk.exe job.chk job.fch"],
                    cwd=str(win_work), capture_output=True, timeout=180,
                )
                if (win_work / "job.fch").exists():
                    shutil.copy(win_work / "job.fch", fchk_local)
            except Exception:
                pass

        fields: dict = {
            "status": "succeeded" if term else "failed",
            "error": "" if term else _extract_gaussian_error(text, rc),
            "message": "Normal termination of Gaussian." if term else "",
        }
        if log_local.exists():
            fields["log_path"] = str(log_local)
        if fchk_local.exists():
            fields["fchk_path"] = str(fchk_local)
        update_job(job_id, **fields)
        try:
            shutil.rmtree(win_work)
        except Exception:
            pass

    threading.Thread(target=watch, daemon=True).start()


def cancel_local(job: dict) -> None:
    pid = job.get("remote_pid")
    if pid:
        try:
            subprocess.run(["kill", str(pid)], check=False)
        except Exception:
            pass
    # For Windows runs, the Linux pid is cmd.exe; g09.exe keeps running, so
    # also taskkill it by image name.
    if job.get("is_windows") and Path(_CMD_EXE).exists():
        try:
            subprocess.run([_CMD_EXE, "/c", "taskkill /F /IM g09.exe"],
                           capture_output=True, timeout=15)
        except Exception:
            pass
    update_job(job["id"], status="cancelled", message="已取消本地任务。")
