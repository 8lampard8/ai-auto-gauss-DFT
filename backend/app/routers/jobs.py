"""Job submission + SSH profile endpoints.

Route order matters: the literal ``/jobs/ssh-profiles`` routes must be
declared before the parameterised ``/jobs/{job_id}`` routes, otherwise the
path param would shadow them.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import psutil
from fastapi import APIRouter, HTTPException

from ..config import LOCAL_MEM_FRACTION, LOCAL_RESERVE_CORES
from ..exec.local_runner import cancel_local, submit_local
from ..exec.ssh_runner import cancel_ssh, submit_ssh
from ..jobs_store import create as create_job, delete as delete_job, get as get_job, list_all
from ..molecules_store import load as load_molecule
from ..schemas import CreateJobRequest, SshProfile
from ..settings_store import (
    _mask_secrets,
    load as load_settings,
    merge_provider_secret,
    save,
)

router = APIRouter(tags=["jobs"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _default_local_resources() -> tuple[int, str]:
    cpu = psutil.cpu_count(logical=False) or 1
    ram = psutil.virtual_memory().total
    nproc = max(1, cpu - LOCAL_RESERVE_CORES)
    mem_mb = max(1024, int(ram * LOCAL_MEM_FRACTION) // (1024**2))
    # Gaussian %mem requires an integer + unit (e.g. 11110MB, 10GB) — decimals
    # like 10.8GB are a syntax error, so emit MB directly.
    return nproc, f"{mem_mb}MB"


def _find_profile(pid: str):
    profiles = load_settings().get("ssh_profiles", [])
    for p in profiles:
        if p.get("id") == pid:
            return SshProfile(**p)
    return None


# ---------------------------------------------------------------------------
# jobs: list + create (no path param -> safe to declare first)
# ---------------------------------------------------------------------------
@router.get("/jobs")
def list_jobs() -> dict:
    return {"jobs": list_all()}


@router.post("/jobs")
def create_job_endpoint(req: CreateJobRequest) -> dict:
    try:
        mol = load_molecule(req.molecule_id)
    except FileNotFoundError:
        raise HTTPException(404, f"molecule {req.molecule_id} not found")

    if req.kind == "local":
        nproc = req.nproc or _default_local_resources()[0]
        mem = req.mem or _default_local_resources()[1]
        gaussian_path = load_settings().get("gaussian_path", "")
    else:
        if not req.ssh_profile_id:
            raise HTTPException(400, "SSH 任务需要 ssh_profile_id")
        profile = _find_profile(req.ssh_profile_id)
        if profile is None:
            raise HTTPException(404, f"ssh profile {req.ssh_profile_id} not found")
        nproc = req.nproc or 4
        mem = req.mem or "8GB"

    job_id = "job-" + uuid.uuid4().hex[:10]
    spec_label = (req.spec.label or f"{req.spec.functional}/{req.spec.basis}")
    if req.gjf:
        spec_label = req.spec.label or "(自定义 gjf)"
    create_job(
        job_id,
        kind=req.kind,
        molecule_id=req.molecule_id,
        molecule_name=mol.name,
        spec_label=spec_label,
        nproc=nproc,
        mem=mem,
        ssh_profile_id=req.ssh_profile_id or "",
    )

    if req.kind == "local":
        submit_local(job_id, mol, req.spec, gaussian_path, nproc, mem,
                     gjf_text=req.gjf or None)
    else:
        submit_ssh(job_id, mol, req.spec, profile, nproc, mem,
                   gjf_text=req.gjf or None)

    return get_job(job_id) or {"id": job_id, "status": "queued"}


# ---------------------------------------------------------------------------
# SSH profiles (literal path -> must come before /jobs/{job_id})
# ---------------------------------------------------------------------------
@router.get("/jobs/ssh-profiles")
def list_ssh_profiles() -> dict:
    s = load_settings()
    return {"ssh_profiles": _mask_secrets(s.get("ssh_profiles", []))}


@router.post("/jobs/ssh-profiles")
def add_ssh_profile(p: SshProfile) -> dict:
    s = load_settings()
    profiles = s.get("ssh_profiles", [])
    if any(x.get("id") == p.id for x in profiles):
        raise HTTPException(409, f"profile id '{p.id}' already exists")
    profiles.append(p.model_dump())
    s["ssh_profiles"] = profiles
    save(s)
    return {"ssh_profiles": _mask_secrets(profiles)}


@router.put("/jobs/ssh-profiles/{pid}")
def update_ssh_profile(pid: str, p: SshProfile) -> dict:
    s = load_settings()
    profiles = s.get("ssh_profiles", [])
    idx = next((i for i, x in enumerate(profiles) if x.get("id") == pid), None)
    if idx is None:
        raise HTTPException(404, f"profile '{pid}' not found")
    merged = merge_provider_secret(profiles, p.model_dump())
    merged["id"] = pid
    profiles[idx] = merged
    s["ssh_profiles"] = profiles
    save(s)
    return {"ssh_profiles": _mask_secrets(profiles)}


@router.delete("/jobs/ssh-profiles/{pid}")
def delete_ssh_profile(pid: str) -> dict:
    s = load_settings()
    s["ssh_profiles"] = [x for x in s.get("ssh_profiles", []) if x.get("id") != pid]
    save(s)
    return {"ssh_profiles": _mask_secrets(s["ssh_profiles"])}


# ---------------------------------------------------------------------------
# jobs: parameterised routes
# ---------------------------------------------------------------------------
@router.get("/jobs/{job_id}")
def get_job_endpoint(job_id: str) -> dict:
    j = get_job(job_id)
    if j is None:
        raise HTTPException(404, f"job {job_id} not found")
    return j


@router.get("/jobs/{job_id}/log")
def get_job_log(job_id: str) -> dict:
    j = get_job(job_id)
    if j is None:
        raise HTTPException(404, f"job {job_id} not found")
    log_path = j.get("log_path") or ""
    text = ""
    if log_path and Path(log_path).exists():
        text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
    return {"log": text, "path": log_path}


@router.get("/jobs/{job_id}/gjf")
def get_job_gjf(job_id: str) -> dict:
    j = get_job(job_id)
    if j is None:
        raise HTTPException(404, f"job {job_id} not found")
    gjf_path = j.get("gjf_path") or ""
    text = ""
    if gjf_path and Path(gjf_path).exists():
        text = Path(gjf_path).read_text(encoding="utf-8", errors="ignore")
    return {"gjf": text, "path": gjf_path}


@router.post("/jobs/{job_id}/cancel")
def cancel_job_endpoint(job_id: str) -> dict:
    j = get_job(job_id)
    if j is None:
        raise HTTPException(404, f"job {job_id} not found")
    if j.get("status") not in ("queued", "running"):
        return j
    if j.get("kind") == "local":
        cancel_local(j)
    else:
        profile = _find_profile(j.get("ssh_profile_id", ""))
        cancel_ssh(j, profile)
    return get_job(job_id) or j


@router.delete("/jobs/{job_id}")
def delete_job_endpoint(job_id: str) -> dict:
    delete_job(job_id)
    return {"ok": True}
