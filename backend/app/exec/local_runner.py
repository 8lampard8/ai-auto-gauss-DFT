"""Local Gaussian runner.

Handles three execution modes:

1. **Linux / macOS Gaussian** (g16 / g09 on PATH or absolute POSIX path): run
   directly via subprocess.
2. **Native Windows Gaussian** (backend running on Windows with g09w.exe /
   g09.exe / g16.exe): run headless with ``GAUSS_EXEDIR`` / ``GAUSS_SCRDIR``
   set in the process environment, substituting GUI launcher ``g09w.exe`` with
   CLI ``g09.exe``.
3. **Windows Gaussian via WSL2 interop** (Linux backend invoking Windows
   G09W): translate path to ``/mnt/<drive>/...``, stage the gjf on the Windows
   drive, and invoke ``g09.exe`` through ``cmd.exe``.

A daemon thread waits for completion, generates ``job.fchk`` via ``formchk``,
extracts a quantum-descriptor summary, and marks the job succeeded only if all
job steps ended with "Normal termination".
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from ..chemistry import gaussian_parser as gp
from ..chemistry.gjf_writer import generate_gjf
from ..config import JOBS_DIR
from ..jobs_store import list_by_status, update as update_job
from .wsl import CMD_EXE, is_windows_path, on_windows, on_wsl, to_linux_path, to_windows_path

# Track active subprocesses so cancel_local terminates only this job.
_PROCS_LOCK = threading.Lock()
_PROCS: dict[str, subprocess.Popen] = {}


def _register_proc(job_id: str, proc: subprocess.Popen) -> None:
    with _PROCS_LOCK:
        _PROCS[job_id] = proc


def _pop_proc(job_id: str) -> subprocess.Popen | None:
    with _PROCS_LOCK:
        return _PROCS.pop(job_id, None)


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
    m = re.match(r"^\s*([\d.]+)\s*(GB|MB|MW|KW)\s*$", mem or "", re.I)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).upper()
    mult = {"GB": 1024.0, "MB": 1.0, "MW": 8.0, "KW": 8.0 / 1024.0}
    return int(round(val * mult[unit]))


def _cap_mem(mem: str, max_mb: int) -> str:
    """If mem exceeds max_mb, clamp it down to ``{max_mb}MB``."""
    mb = _mem_to_mb(mem)
    if mb is not None and mb > max_mb:
        return f"{max_mb}MB"
    return mem


def _is_g09w(gaussian_path: str) -> bool:
    """Gaussian 09 for Windows is 32-bit (IA32W) and can't address >~2GB."""
    return "g09w" in gaussian_path.lower()


_BASIS_WEIGHTS = {
    "def2-svp": 15, "def2svp": 15, "6-31g(d)": 15, "6-31g*": 15,
    "6-31g(d,p)": 16, "6-31g**": 16, "6-311g(d,p)": 25, "6-311g**": 25,
    "def2-tzvp": 30, "def2tzvp": 30, "ma-def2-tzvp": 32,
    "def2-tzvpp": 40, "def2tzvpp": 40, "cc-pvtz": 40,
    "aug-cc-pvtz": 55, "def2-qzvpp": 60, "def2qzvpp": 60,
}


def _estimate_basis_functions(n_atoms: int, basis: str) -> int:
    """Rough basis-function count for a pre-flight G09W feasibility check."""
    return n_atoms * _BASIS_WEIGHTS.get((basis or "").lower(), 25)


def _cap_gjf_text(text: str, max_mem_mb: int = 1500, max_nproc: int = 4) -> str:
    """Patch %mem / %nprocshared in a gjf text for G09W (32-bit, 4-core)."""
    m = re.search(r"%mem\s*=\s*([^\r\n]+)", text, re.I)
    if m:
        mb = _mem_to_mb(m.group(1).strip())
        if mb is not None and mb > max_mem_mb:
            text = re.sub(r"%mem\s*=\s*[^\r\n]+", f"%mem={max_mem_mb}MB", text, flags=re.I)
    m = re.search(r"%nprocshared\s*=\s*(\d+)", text, re.I)
    if m and int(m.group(1)) > max_nproc:
        text = re.sub(r"%nprocshared\s*=\s*\d+", f"%nprocshared={max_nproc}", text, flags=re.I)
    return text


def _patch_gjf_resources(gjf_path: Path, mem: str, nproc: int) -> None:
    """Rewrite the %mem / %nprocshared lines in a staged gjf (for retries)."""
    g = gjf_path.read_text(encoding="utf-8")
    g = re.sub(r"%mem\s*=.*", f"%mem={mem}", g, flags=re.I)
    g = re.sub(r"%nprocshared\s*=.*", f"%nprocshared={nproc}", g, flags=re.I)
    gjf_path.write_text(g, encoding="utf-8")


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
def submit_local(job_id: str, molecule, spec, gaussian_path: str,
                 nproc: int, mem: str, gjf_text: str | None = None) -> None:
    work = JOBS_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)
    extra_note = ""

    if gjf_text:
        gjf = gjf_text
        if is_windows_path(gaussian_path) and _is_g09w(gaussian_path):
            capped = _cap_gjf_text(gjf)
            if capped != gjf:
                extra_note += "G09W 为 32 位,已将编辑后 gjf 的 %mem/%nprocshared 限制为 1500MB/4 核;"
                gjf = capped
        m_np = re.search(r"%nprocshared\s*=\s*(\d+)", gjf, re.I)
        m_mem = re.search(r"%mem\s*=\s*(\S+)", gjf, re.I)
        rec_nproc = int(m_np.group(1)) if m_np else nproc
        rec_mem = m_mem.group(1) if m_mem else mem
    else:
        spec.nproc = nproc
        spec.memory = _sanitize_mem(mem)

        # G09W is 32-bit (IA32W) with a 4-core license: clamp %mem (<=~1.5GB)
        # and %nprocshared (<=4).
        if is_windows_path(gaussian_path) and _is_g09w(gaussian_path):
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
        rec_nproc = spec.nproc
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

    if on_windows():
        _submit_native_windows(job_id, work, gjf_path, gaussian_path, extra_note)
    elif is_windows_path(gaussian_path) and on_wsl():
        _submit_wsl_windows(job_id, work, gjf_path, gaussian_path, extra_note)
    else:
        _submit_linux(job_id, work, gjf_path, gaussian_path)


# ---------------------------------------------------------------------------
# Linux / POSIX Gaussian
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

    _register_proc(job_id, proc)
    update_job(job_id, status="running", log_path=str(log_path),
               remote_pid=str(proc.pid))

    def watch() -> None:
        try:
            rc = proc.wait()
        finally:
            _pop_proc(job_id)
            try:
                log_fp.close()
            except Exception:
                pass
        text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        term = gp.terminated_normally(text)
        if term:
            fields: dict = {
                "status": "succeeded",
                "error": "",
                "message": "Normal termination of Gaussian.",
                "summary": gp.summarize(text),
            }
            fchk = _linux_formchk(work, gaussian_path)
            if fchk:
                fields["fchk_path"] = str(fchk)
            update_job(job_id, _skip_if_status=("cancelled",), **fields)
        else:
            update_job(job_id, _skip_if_status=("cancelled",),
                       status="failed", error=gp.extract_gaussian_error(text, rc))

    threading.Thread(target=watch, daemon=True).start()


def _linux_formchk(work: Path, gaussian_path: str) -> Path | None:
    """Best-effort formchk on Linux after a successful run."""
    formchk_exe = Path(gaussian_path).resolve().parent / "formchk"
    if not formchk_exe.exists():
        found = shutil.which("formchk")
        if not found:
            return None
        formchk_exe = Path(found)
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
# Native Windows Gaussian (G09W / G16W)
# ---------------------------------------------------------------------------
def _resolve_win_cli(gaussian_path: str) -> tuple[Path, Path, str]:
    """Return (exe_path, exedir, note). Maps GUI launcher g09w.exe -> g09.exe."""
    p = Path(gaussian_path)
    note = ""
    low = p.name.lower()
    if low == "g09w.exe":
        p = p.with_name("g09.exe")
        note = "检测到 g09w.exe(GUI 启动器),自动改用 g09.exe(命令行)执行。"
    elif low == "g16w.exe":
        p = p.with_name("g16.exe")
        note = "检测到 g16w.exe(GUI 启动器),自动改用 g16.exe(命令行)执行。"
    return p, p.parent, note


def _submit_native_windows(job_id: str, work: Path, gjf_path: Path,
                           gaussian_path: str, extra_note: str = "") -> None:
    exe_path, exedir, note = _resolve_win_cli(gaussian_path)
    if extra_note:
        note = (note + " " + extra_note).strip()
    if not exe_path.exists():
        update_job(job_id, status="failed",
                   error=f"未找到 Gaussian 可执行文件:{exe_path}。请在「设置」中确认路径。")
        return

    log_path = work / "job.log"
    env = os.environ.copy()
    env["GAUSS_EXEDIR"] = str(exedir)
    env["GAUSS_SCRDIR"] = str(work)

    update_job(job_id, status="running", is_windows=True,
               message=(note + f" 直接调用 {exe_path}").strip(),
               work_dir=str(work), log_path=str(log_path))

    def _run_once() -> tuple[int, str]:
        try:
            proc = subprocess.Popen([str(exe_path), "job.gjf", "job.log"],
                                    cwd=str(work), env=env)
        except Exception as e:
            return -1, f"启动失败:{e}"
        _register_proc(job_id, proc)
        update_job(job_id, _skip_if_status=("cancelled",), remote_pid=str(proc.pid))
        try:
            rc = proc.wait()
        finally:
            _pop_proc(job_id)
        text = log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""
        return rc, text

    def watch() -> None:
        rc, text = _run_once()
        term = gp.terminated_normally(text)

        if not term and gp.is_link0_crash(text):
            update_job(job_id, _skip_if_status=("cancelled",),
                       message="检测到 G09W link0 崩溃,以 nproc=1/mem=600MB 重试中…")
            _patch_gjf_resources(gjf_path, "600MB", 1)
            rc, text = _run_once()
            term = gp.terminated_normally(text)

        fchk_path = work / "job.fchk"
        if term and (work / "job.chk").exists():
            formchk = exedir / "formchk.exe"
            if formchk.exists():
                try:
                    subprocess.run([str(formchk), "job.chk", "job.fchk"],
                                   cwd=str(work), env=env, capture_output=True, timeout=180)
                except Exception:
                    pass

        fields: dict = {
            "status": "succeeded" if term else "failed",
            "error": "" if term else gp.extract_gaussian_error(text, rc),
            "message": "Normal termination of Gaussian." if term else "",
        }
        if term:
            fields["summary"] = gp.summarize(text)
        if fchk_path.exists():
            fields["fchk_path"] = str(fchk_path)
        update_job(job_id, _skip_if_status=("cancelled",), **fields)

    threading.Thread(target=watch, daemon=True).start()


# ---------------------------------------------------------------------------
# Windows Gaussian (G09W) via WSL interop
# ---------------------------------------------------------------------------
def _run_g09w_wsl(job_id: str, win_work: Path, exe_win: str, exedir_win: str,
                  win_work_win: str) -> tuple[int, str]:
    """Run one g09.exe pass via cmd.exe; return (exit_code, log_text)."""
    cmd = (
        f"set GAUSS_EXEDIR={exedir_win}&& "
        f"set GAUSS_SCRDIR={win_work_win}&& "
        f"\"{exe_win}\" job.gjf job.log"
    )
    try:
        proc = subprocess.Popen([CMD_EXE, "/c", cmd], cwd=str(win_work))
    except Exception as e:
        return -1, f"启动失败:{e}"
    _register_proc(job_id, proc)
    update_job(job_id, _skip_if_status=("cancelled",), remote_pid=str(proc.pid))
    try:
        rc = proc.wait()
    finally:
        _pop_proc(job_id)
    win_log = win_work / "job.log"
    text = win_log.read_text(encoding="utf-8", errors="ignore") if win_log.exists() else ""
    return rc, text


def _submit_wsl_windows(job_id: str, work: Path, gjf_path: Path,
                        gaussian_path: str, extra_note: str = "") -> None:
    if not Path(CMD_EXE).exists():
        update_job(job_id, status="failed",
                   error="当前非 WSL2 环境,无法调用 Windows 版 Gaussian。"
                         "请在 Linux 上安装 Gaussian,或改用 SSH 提交。")
        return

    norm = gaussian_path.replace("/", "\\")
    parts = norm.split("\\")
    basename = parts[-1]
    dirname_win = "\\".join(parts[:-1])
    note = ""
    if basename.lower() == "g09w.exe":
        basename = "g09.exe"
        note = "检测到 g09w.exe(GUI 启动器),自动改用 g09.exe(命令行)执行。"
    elif basename.lower() == "g16w.exe":
        basename = "g16.exe"
        note = "检测到 g16w.exe(GUI 启动器),自动改用 g16.exe(命令行)执行。"
    if extra_note:
        note = (note + " " + extra_note).strip()
    exe_win = dirname_win + "\\" + basename
    exe_linux = to_linux_path(exe_win)
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
    win_work_win = to_windows_path(str(win_work))

    update_job(job_id, status="running", is_windows=True,
               message=(note + f" 通过 WSL interop 调用 {exe_win}").strip(),
               work_dir=str(work),
               log_path=str(win_work / "job.log"))

    def watch() -> None:
        rc, text = _run_g09w_wsl(job_id, win_work, exe_win, exedir_win, win_work_win)
        term = gp.terminated_normally(text)

        if not term and gp.is_link0_crash(text):
            update_job(job_id, _skip_if_status=("cancelled",),
                       message="检测到 G09W link0 崩溃,以 nproc=1/mem=600MB 重试中…")
            _patch_gjf_resources(win_work / "job.gjf", "600MB", 1)
            rc, text = _run_g09w_wsl(job_id, win_work, exe_win, exedir_win, win_work_win)
            term = gp.terminated_normally(text)

        log_local = work / "job.log"
        if (win_work / "job.log").exists():
            shutil.copy(win_work / "job.log", log_local)

        fchk_local = work / "job.fchk"
        if term and (win_work / "job.chk").exists():
            try:
                subprocess.run(
                    [CMD_EXE, "/c",
                     f"set GAUSS_EXEDIR={exedir_win}&& "
                     f"\"{exedir_win}\\formchk.exe\" job.chk job.fch"],
                    cwd=str(win_work), capture_output=True, timeout=180,
                )
                if (win_work / "job.fch").exists():
                    shutil.copy(win_work / "job.fch", fchk_local)
            except Exception:
                pass

        fields: dict = {
            "status": "succeeded" if term else "failed",
            "error": "" if term else gp.extract_gaussian_error(text, rc),
            "message": "Normal termination of Gaussian." if term else "",
        }
        if term:
            fields["summary"] = gp.summarize(text)
        if log_local.exists():
            fields["log_path"] = str(log_local)
        if fchk_local.exists():
            fields["fchk_path"] = str(fchk_local)
        update_job(job_id, _skip_if_status=("cancelled",), **fields)
        try:
            shutil.rmtree(win_work)
        except Exception:
            pass

    threading.Thread(target=watch, daemon=True).start()


# ---------------------------------------------------------------------------
# cancellation & startup orphan recovery
# ---------------------------------------------------------------------------
def cancel_local(job: dict) -> None:
    job_id = job["id"]
    # Mark cancelled first so the watcher thread doesn't race and mark "failed".
    update_job(job_id, status="cancelled", message="已取消本地任务。")

    proc = _pop_proc(job_id)
    pid = str(proc.pid) if proc else (job.get("remote_pid") or "")

    if on_windows():
        if pid:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                               capture_output=True, timeout=15)
            except Exception:
                pass
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
    else:
        if pid:
            try:
                subprocess.run(["kill", pid], check=False)
            except Exception:
                pass
        if job.get("is_windows") and Path(CMD_EXE).exists():
            try:
                subprocess.run([CMD_EXE, "/c", "taskkill /F /IM g09.exe"],
                               capture_output=True, timeout=15)
            except Exception:
                pass


def reconcile_orphaned_jobs() -> None:
    """Reconcile local jobs left in 'running' state after a server restart."""
    import psutil

    for j in list_by_status("running"):
        if j.get("kind") != "local":
            continue
        pid_str = j.get("remote_pid") or ""
        alive = False
        if pid_str.isdigit():
            try:
                alive = psutil.pid_exists(int(pid_str))
            except Exception:
                alive = False
        if alive:
            continue
        log_path = j.get("log_path") or ""
        text = ""
        if log_path and Path(log_path).exists():
            try:
                text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
        if text and gp.terminated_normally(text):
            update_job(j["id"], status="succeeded", error="",
                       message="Normal termination (recovered on restart).",
                       summary=gp.summarize(text))
        else:
            update_job(j["id"], status="failed",
                       error="服务重启时该本地任务进程已不存在(可能已异常中断)。")
