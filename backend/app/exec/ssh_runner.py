"""Remote Gaussian runner over SSH (paramiko).

Flow: connect (key or password) -> resolve remote $HOME -> mkdir remote scratch
-> upload gjf -> ``nohup g16 job.gjf > job.log 2>&1 &`` -> capture remote PID
-> poll ``kill -0`` until the process exits -> run remote ``formchk`` ->
download job.log (and job.fchk if present) -> extract summary & mark succeeded
only if all steps ended with "Normal termination".
"""
from __future__ import annotations

import shlex
import threading
import time
from pathlib import Path

from ..chemistry import gaussian_parser as gp
from ..chemistry.gjf_writer import generate_gjf
from ..config import JOBS_DIR
from ..jobs_store import get as get_job, update as update_job


def _connect(profile):
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = {
        "hostname": profile.host,
        "port": profile.port,
        "username": profile.user,
        "timeout": 15,
    }
    if profile.key_path:
        kwargs["key_filename"] = profile.key_path
    elif profile.password:
        kwargs["password"] = profile.password
    else:
        kwargs["allow_agent"] = True
        kwargs["look_for_keys"] = True
    client.connect(**kwargs)
    return client


def _resolve_remote_dir(client, raw_dir: str) -> str:
    """Expand leading ``$HOME`` or ``~`` on the remote host so SFTP (which does
    not perform shell expansion) receives an absolute path."""
    d = (raw_dir or "$HOME/gaussian_jobs").strip().rstrip("/")
    if d.startswith("$HOME") or d.startswith("~"):
        _, out, _ = client.exec_command('printf "%s" "$HOME"')
        home = out.read().decode("utf-8", errors="ignore").strip()
        if home:
            if d.startswith("$HOME"):
                d = home + d[len("$HOME"):]
            elif d.startswith("~"):
                d = home + d[1:]
    return d


def submit_ssh(job_id: str, molecule, spec, profile, nproc: int, mem: str,
               gjf_text: str | None = None) -> None:
    work = JOBS_DIR / job_id
    work.mkdir(parents=True, exist_ok=True)
    if gjf_text:
        gjf = gjf_text
    else:
        spec.nproc = nproc
        spec.memory = mem
        try:
            gjf = generate_gjf(molecule, spec)
        except ValueError as e:
            update_job(job_id, status="failed", error=str(e))
            return
    gjf_path = work / "job.gjf"
    gjf_path.write_text(gjf, encoding="utf-8")
    update_job(job_id, gjf_path=str(gjf_path), work_dir=str(work),
               remote_host=profile.host, nproc=nproc, mem=mem)

    try:
        client = _connect(profile)
    except Exception as e:
        update_job(job_id, status="failed", error=f"SSH 连接失败:{e}")
        return

    try:
        base_dir = _resolve_remote_dir(client, profile.scratch_dir)
        remote_scratch = f"{base_dir}/{job_id}"
        q_scratch = shlex.quote(remote_scratch)
        q_gauss = shlex.quote(profile.gaussian_path or "g16")

        _, mk_out, mk_err = client.exec_command(f"mkdir -p -- {q_scratch}")
        if mk_out.channel.recv_exit_status() != 0:
            err_msg = mk_err.read().decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"创建远程目录失败 ({remote_scratch}): {err_msg}")

        sftp = client.open_sftp()
        try:
            sftp.put(str(gjf_path), f"{remote_scratch}/job.gjf")
        finally:
            sftp.close()

        cmd = (
            f"cd -- {q_scratch} && "
            f"nohup {q_gauss} job.gjf > job.log 2>&1 < /dev/null & echo $!"
        )
        _, stdout, _ = client.exec_command(cmd)
        pid = stdout.read().decode("utf-8", errors="ignore").strip()
        if not pid.isdigit():
            raise RuntimeError(f"远程启动未返回有效 PID: {pid!r}")

        update_job(job_id, status="running", remote_pid=pid,
                   remote_scratch=remote_scratch,
                   message=f"已提交到 {profile.host}:{profile.port},远程 PID {pid}")
    except Exception as e:
        update_job(job_id, status="failed", error=f"SSH 提交失败:{e}")
        client.close()
        return

    def poll() -> None:
        q_scratch = shlex.quote(remote_scratch)
        try:
            for _ in range(3600):  # ~6h at 6s cadence
                cur = get_job(job_id)
                if cur is None or cur.get("status") == "cancelled":
                    return
                try:
                    _, out, _ = client.exec_command(
                        f"kill -0 {int(pid)} 2>/dev/null && echo RUN || echo DONE"
                    )
                    state = out.read().decode("utf-8", errors="ignore").strip()
                except Exception:
                    state = "DONE"
                if state != "RUN":
                    break
                time.sleep(6)

            # Best-effort formchk on the remote host if job.chk was produced.
            try:
                _, fc_out, _ = client.exec_command(
                    f"cd -- {q_scratch} && "
                    f"[ -f job.chk ] && [ ! -f job.fchk ] && "
                    f"(command -v formchk >/dev/null 2>&1 && formchk job.chk job.fchk || true)"
                )
                fc_out.channel.recv_exit_status()
            except Exception:
                pass

            # Download results
            log_local = work / "job.log"
            fchk_local = work / "job.fchk"
            try:
                sftp2 = client.open_sftp()
                try:
                    sftp2.get(f"{remote_scratch}/job.log", str(log_local))
                    try:
                        sftp2.get(f"{remote_scratch}/job.fchk", str(fchk_local))
                    except Exception:
                        pass
                finally:
                    sftp2.close()
            except Exception as e:
                update_job(job_id, _skip_if_status=("cancelled",),
                           status="failed", error=f"下载日志失败:{e}")
                return

            text = log_local.read_text(encoding="utf-8", errors="ignore")
            term = gp.terminated_normally(text)
            fields: dict = {
                "status": "succeeded" if term else "failed",
                "log_path": str(log_local),
                "error": "" if term else gp.extract_gaussian_error(text, None),
                "message": "Normal termination (remote)." if term else "",
            }
            if term:
                fields["summary"] = gp.summarize(text)
            if fchk_local.exists():
                fields["fchk_path"] = str(fchk_local)
            update_job(job_id, _skip_if_status=("cancelled",), **fields)
        finally:
            try:
                client.close()
            except Exception:
                pass

    threading.Thread(target=poll, daemon=True).start()


def cancel_ssh(job: dict, profile) -> None:
    update_job(job["id"], status="cancelled", message="正在取消远程任务…")
    pid = str(job.get("remote_pid") or "").strip()
    if not pid.isdigit() or not profile:
        update_job(job["id"], status="cancelled", message="已取消远程任务。")
        return
    try:
        client = _connect(profile)
        try:
            client.exec_command(f"kill {int(pid)} 2>/dev/null || true")
        finally:
            client.close()
    except Exception as e:
        update_job(job["id"], status="cancelled", message=f"取消时连接失败:{e}")
        return
    update_job(job["id"], status="cancelled", message="已发送 kill 到远程任务。")
