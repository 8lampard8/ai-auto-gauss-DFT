"""Visualization endpoints: recipe catalog + run Multiwfn/VMD pipeline.

Writes are sandboxed to the configured Multiwfn directory and VMD directory
(plus the app data tree). The .fchk comes from a finished job (formchk) or a
user-supplied path.
"""
from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..chemistry.plot_recipes import RECIPES, get_recipe
from ..exec.multiwfn_runner import run as run_multiwfn
from ..exec.vmd_runner import render as render_vmd
from ..exec.wsl import tool_dir
from ..jobs_store import get as get_job
from ..molecules_store import load as load_molecule
from ..security import assert_writable, is_within
from ..settings_store import load as load_settings

router = APIRouter(tags=["visualize"])


def _fchk_counts(fchk_path: Path) -> tuple[int | None, int | None]:
    """Read (n_atoms, n_alpha_electrons) directly from a Gaussian .fchk header."""
    try:
        head = fchk_path.read_text(encoding="utf-8", errors="ignore")[:8192]
    except Exception:
        return None, None
    m_at = re.search(r"Number of atoms\s+I\s+(\d+)", head)
    m_al = re.search(r"Number of alpha electrons\s+I\s+(\d+)", head)
    return (int(m_at.group(1)) if m_at else None,
            int(m_al.group(1)) if m_al else None)


def _atomic_num(element: str) -> int:
    try:
        from rdkit import Chem
        z = Chem.GetPeriodicTable().GetAtomicNumber(element)
        if z > 0:
            return z
    except Exception:
        pass
    return 6


class VisualizeRequest(BaseModel):
    job_id: str
    recipe: str
    multiwfn_input: list[str] | None = None
    vmd_script: str | None = None


def _dirs() -> tuple[str, str, Path, Path]:
    s = load_settings()
    mw = s.get("multiwfn_path", "")
    vmd = s.get("vmd_path", "")
    if not mw:
        raise HTTPException(400, "未配置 Multiwfn 路径(请在「设置」中填写)")
    # tool_dir translates Windows paths to /mnt and returns the install dir,
    # so the sandbox work dirs land on the Windows drive (Windows tools can
    # read/write them).
    mw_dir = tool_dir(mw)
    vmd_dir = tool_dir(vmd) if vmd else mw_dir
    return mw, vmd, mw_dir, vmd_dir


@router.get("/visualize/recipes")
def list_recipes() -> dict:
    out = {}
    for k, v in RECIPES.items():
        out[k] = {
            "label": v["label"],
            "needs": v["needs"],
            "multiwfn_input": v["multiwfn_input"],
            "multiwfn_note": v["multiwfn_note"],
            "vmd_script": v["vmd_script"],
            "instructions": v["instructions"],
            "cubes": v.get("cubes", []),
        }
    return {"recipes": out}


@router.post("/visualize/run")
def run(req: VisualizeRequest) -> dict:
    mw_path, vmd_path, mw_dir, vmd_dir = _dirs()
    recipe = get_recipe(req.recipe)
    if recipe is None:
        raise HTTPException(400, f"未知作图类型:{req.recipe}")

    job = get_job(req.job_id)
    if job is None:
        raise HTTPException(404, f"job {req.job_id} not found")
    fchk_src = job.get("fchk_path", "")
    if not fchk_src or not Path(fchk_src).exists():
        raise HTTPException(
            400,
            "任务尚无 .fchk。请确保任务成功完成并生成了 formchk(.fchk),"
            "或使用带 %chk 的 gjf 并在成功后运行 formchk。",
        )

    input_lines = list(req.multiwfn_input or recipe["multiwfn_input"])
    # Substitute placeholders: {atoms} (IGMH), {homo}/{lumo} (orbital indices).
    # Prefer exact counts from the .fchk header; fall back to the saved molecule.
    n_atoms, n_occ = _fchk_counts(Path(fchk_src))
    if n_atoms is None or n_occ is None:
        try:
            mol = load_molecule(job.get("molecule_id", ""))
            if n_atoms is None:
                n_atoms = len(mol.atoms)
            if n_occ is None:
                n_elec = sum(_atomic_num(a.element) for a in mol.atoms) - mol.charge
                n_occ = max(1, (n_elec + mol.multiplicity - 1) // 2)
        except Exception:
            pass
    if n_atoms and n_occ:
        subs = {
            "{atoms}": f"1-{n_atoms}",
            "{homo}": str(n_occ),
            "{lumo}": str(n_occ + 1),
        }
        for k, v in subs.items():
            input_lines = [l.replace(k, v) for l in input_lines]
    vmd_script = req.vmd_script or recipe["vmd_script"]
    run_id = uuid.uuid4().hex[:10]

    # sandboxed work dir inside the Multiwfn directory
    mw_work = mw_dir / "aagd_work" / run_id
    assert_writable(mw_work, [mw_dir])
    mw_work.mkdir(parents=True, exist_ok=True)
    fchk_local = mw_work / "system.fch"
    shutil.copy(fchk_src, fchk_local)

    mw_log = run_multiwfn(mw_path, fchk_local, mw_work, input_lines)

    # collect cubes into the VMD directory (sandboxed)
    vmd_out = vmd_dir / "aagd_plots" / run_id
    assert_writable(vmd_out, [vmd_dir])
    vmd_out.mkdir(parents=True, exist_ok=True)
    cubes: list[str] = []
    for c in mw_work.glob("*.cub"):
        shutil.copy(c, vmd_out / c.name)
        cubes.append(c.name)

    png_path = vmd_out / f"{req.recipe}.png"
    vmd_log = ""
    image_url = None
    if vmd_path:
        vmd_log, ok = render_vmd(vmd_path, vmd_out, vmd_script, png_path)
        if ok and png_path.exists():
            image_url = f"/api/visualize/image/{run_id}/{req.recipe}.png"

    return {
        "run_id": run_id,
        "recipe": req.recipe,
        "multiwfn_log": mw_log[-4000:],
        "vmd_log": vmd_log[-2000:],
        "cubes": cubes,
        "image_url": image_url,
        "instructions": recipe["instructions"],
        "vmd_out_dir": str(vmd_out),
    }


@router.get("/visualize/image/{run_id}/{name}")
def get_image(run_id: str, name: str) -> FileResponse:
    s = load_settings()
    base_tool = s.get("vmd_path") or s.get("multiwfn_path", "")
    if not base_tool:
        raise HTTPException(400, "未配置 VMD / Multiwfn 路径")
    vmd_dir = tool_dir(base_tool)
    img = (vmd_dir / "aagd_plots" / run_id / name).resolve()
    # strict sandbox: only allow png/jpg/tga inside aagd_plots
    if not name.lower().endswith((".png", ".jpg", ".jpeg", ".tga")):
        raise HTTPException(400, "不支持的图像类型")
    if not is_within(img, vmd_dir / "aagd_plots"):
        raise HTTPException(403, "路径越界")
    if not img.exists():
        raise HTTPException(404, "图像尚未生成")
    return FileResponse(str(img))
