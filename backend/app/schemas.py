"""Shared Pydantic models.

Kept intentionally small at the scaffold stage; routers extend it as they
gain real behaviour.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Health(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    version: str = ""


class SystemInfo(BaseModel):
    platform: str = ""
    python: str = ""
    cpu_count: int = 0              # physical cores
    cpu_count_logical: int = 0
    cpu_freq_mhz: Optional[float] = None
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0


class LocalResourceSuggestion(BaseModel):
    """Recommended %nproc / %mem for a local Gaussian job."""
    nproc: int
    mem_mb: int                     # Gaussian %mem in MB
    mem_human: str                  # e.g. "16GB"
    ram_total_gb: float
    cpu_count: int
    note: str = ""


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    messages: list[Message] = Field(default_factory=list)
    provider_id: Optional[str] = None
    model: Optional[str] = None
    context: dict = Field(default_factory=dict)   # molecule_id, job_id, ...


# ---------------------------------------------------------------------------
# Molecules
# ---------------------------------------------------------------------------
class Atom(BaseModel):
    element: str
    x: float
    y: float
    z: float


class Bond(BaseModel):
    a1: int
    a2: int
    order: float = 1.0


class Molecule(BaseModel):
    id: str
    name: str = ""
    source: str = ""               # smiles|mol|mol2|gjf|out|cdxml|image
    charge: int = 0
    multiplicity: int = 1
    atoms: list[Atom] = Field(default_factory=list)
    bonds: list[Bond] = Field(default_factory=list)
    smiles: str = ""
    molblock: str = ""             # SDF/MOL block (preferred for the viewer)
    xyz: str = ""                  # XYZ fallback (3Dmol infers bonds)
    route: str = ""                # route section if known (gjf/out)
    title: str = ""
    created_at: str = ""


class MoleculeSummary(BaseModel):
    id: str
    name: str = ""
    source: str = ""
    formula: str = ""
    natoms: int = 0
    charge: int = 0
    multiplicity: int = 1


class ImportRequest(BaseModel):
    source: Literal["smiles", "mol", "mol2", "gjf", "out", "cdxml", "image"]
    content: str                   # text content, or base64 data for images
    filename: str = ""
    mime: str = ""                 # for images
    name: str = ""
    # image-only: use a specific provider/model for vision recognition
    # (defaults to the active provider). Lets the user pick a vision-capable
    # model when the active one is text-only.
    provider_id: str = ""
    model: str = ""


class ImportByNameRequest(BaseModel):
    name: str                      # molecule name (CN/EN) to resolve via PubChem/CIR


class UpdateStructureRequest(BaseModel):
    smiles: str                    # new SMILES; re-embeds 3D, keeps the same molecule id


# ---------------------------------------------------------------------------
# gjf generation / method recommendation
# ---------------------------------------------------------------------------
class MethodSpec(BaseModel):
    functional: str = "B3LYP"      # Gaussian route token, e.g. B3LYP / wB97XD / M06-2X
    basis: str = "def2-TZVP"
    route: str = "opt freq"        # base route keywords (opt/freq/td/...)
    dispersion: str = "em=gd3bj"   # empirical dispersion keyword ("" if built-in)
    scrf: str = ""                 # e.g. scrf=(pcm,solvent=water)
    extra: str = ""                # additional keywords
    charge: int = 0
    multiplicity: int = 1
    memory: str = "8GB"
    nproc: int = 4
    title: str = ""
    label: str = ""                # human label, e.g. B3LYP-D3(BJ)/def2-TZVP
    explanation: str = ""


class RecommendRequest(BaseModel):
    molecule_id: str
    task: str = "optfreq"
    solvent: str = ""
    accuracy: Literal["fast", "standard", "high"] = "standard"
    charge: int | None = None
    multiplicity: int | None = None


class GenerateGjfRequest(BaseModel):
    molecule_id: str
    spec: MethodSpec


# ---------------------------------------------------------------------------
# Jobs / submission
# ---------------------------------------------------------------------------
class SshProfile(BaseModel):
    id: str
    name: str = ""
    host: str
    port: int = 22
    user: str
    key_path: str = ""          # preferred auth
    password: str = ""          # fallback (discouraged)
    gaussian_path: str = "g16"
    scratch_dir: str = "$HOME/gaussian_jobs"


class CreateJobRequest(BaseModel):
    molecule_id: str
    kind: Literal["local", "ssh"] = "local"
    spec: MethodSpec
    ssh_profile_id: str = ""
    nproc: int | None = None
    mem: str | None = None       # e.g. "8GB"
