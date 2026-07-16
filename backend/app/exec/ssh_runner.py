"""Remote Gaussian runner over SSH (paramiko).

Flow: connect (key or password) -> mkdir remote scratch -> upload gjf ->
``nohup g16 job.gjf > job.log 2>&1 &`` -> capture remote PID -> poll
``kill -0`` until the process exits -> download job.log (and job.fchk if
present) -> mark succeeded if "Normal termination" appears.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from ..chemistry.gjf_writer import generate_gjf
from ..config import JOBS_DIR
from ..jobs_store import update as update_job


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
        remote_scratch = profile.scratch_dir.rstrip("/") + "/" + job_id
        client.exec_command(f"mkdir -p {remote_scratch}")
        sftp = client.open_sftp()
        remote_gjf = remote_scratch + "/job.gjf"
        sftp.put(str(gjf_path), remote_gjf)
        sftp.close()
        cmd = (
            f"cd {remote_scratch} && "
            f"nohup {profile.gaussian_path} job.gjf > job.log 2>&1 & echo $!"
        )
        _, stdout, _ = client.exec_command(cmd)
        pid = stdout.read().decode().strip()
        update_job(job_id, status="running", remote_pid=pid,
                   message=f"已提交到 {profile.host}:{profile.port},远程 PID {pid}")
    except Exception as e:
        update_job(job_id, status="failed", error=f"SSH 提交失败:{e}")
        client.close()
        return

    def poll() -> None:
        try:
            for _ in range(3600):  # ~6h at 6s cadence
                try:
                    _, out, _ = client.exec_command(
                        f"kill -0 {pid} 2>/dev/null && echo RUN || echo DONE"
                    )
                    state = out.read().decode().strip()
                except Exception:
                    state = "DONE"
                if state != "RUN":
                    break
                time.sleep(6)
            # download results
            log_local = work / "job.log"
            try:
                sftp2 = client.open_sftp()
                sftp2.get(remote_scratch + "/job.log", str(log_local))
                try:
                    sftp2.get(remote_scratch + "/job.fchk", str(work / "job.fchk"))
                    update_job(job_id, fchk_path=str(work / "job.fchk"))
                except Exception:
                    pass
                sftp2.close()
            except Exception as e:
                update_job(job_id, status="failed", error=f"下载日志失败:{e}")
                client.close()
                return
            text = log_local.read_text(encoding="utf-8", errors="ignore")
            term = "Normal termination" in text
            update_job(
                job_id,
                status="succeeded" if term else "failed",
                log_path=str(log_local),
                error="" if term else "远程任务结束,未见 Normal termination。",
            )
        finally:
            try:
                client.close()
            except Exception:
                pass

    threading.Thread(target=poll, daemon=True).start()


def cancel_ssh(job: dict, profile) -> None:
    pid = job.get("remote_pid")
    if not pid or not profile:
        update_job(job["id"], status="cancelled")
        return
    try:
        client = _connect(profile)
        client.exec_command(f"kill {pid} 2>/dev/null || true")
        client.close()
    except Exception as e:
        update_job(job["id"], status="cancelled", message=f"取消时连接失败:{e}")
        return
    update_job(job["id"], status="cancelled", message="已发送 kill 到远程任务。")
