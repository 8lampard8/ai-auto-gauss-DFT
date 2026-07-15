"""System endpoints: health check + local hardware probe.

The hardware probe powers the local resource recommender (CPU/RAM -> %nproc
/ %mem) used when submitting Gaussian jobs locally.
"""
from __future__ import annotations

import platform

import psutil
from fastapi import APIRouter

from .. import __version__
from ..config import LOCAL_MEM_FRACTION, LOCAL_RESERVE_CORES
from ..schemas import Health, LocalResourceSuggestion, SystemInfo

router = APIRouter(tags=["system"])


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok", version=__version__)


@router.get("/system/info", response_model=SystemInfo)
def system_info() -> SystemInfo:
    vm = psutil.virtual_memory()
    freq = psutil.cpu_freq()
    return SystemInfo(
        platform=platform.platform(),
        python=platform.python_version(),
        cpu_count=psutil.cpu_count(logical=False) or 1,
        cpu_count_logical=psutil.cpu_count(logical=True) or 1,
        cpu_freq_mhz=freq.max if freq else None,
        ram_total_gb=round(vm.total / 1024**3, 1),
        ram_available_gb=round(vm.available / 1024**3, 1),
    )


@router.get("/system/local-resources", response_model=LocalResourceSuggestion)
def local_resource_suggestion() -> LocalResourceSuggestion:
    """Recommend %nproc and %mem for a local Gaussian run."""
    info = system_info()
    nproc = max(1, info.cpu_count - LOCAL_RESERVE_CORES)
    mem_bytes = int(info.ram_total_gb * 1024**3 * LOCAL_MEM_FRACTION)
    mem_mb = max(1024, mem_bytes // (1024**2))
    # Gaussian %mem needs an integer + unit; emit MB so it's always valid.
    mem_human = f"{mem_mb}MB"
    return LocalResourceSuggestion(
        nproc=nproc,
        mem_mb=mem_mb,
        mem_human=mem_human,
        ram_total_gb=info.ram_total_gb,
        cpu_count=info.cpu_count,
        note=f"Reserved {LOCAL_RESERVE_CORES} cores; capped %mem at "
             f"{int(LOCAL_MEM_FRACTION*100)}% of total RAM.",
    )
