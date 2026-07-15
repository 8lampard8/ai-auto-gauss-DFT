"""Visualization endpoints: recipe catalog + run Multiwfn/VMD pipeline.

Writes are sandboxed to the configured Multiwfn directory and VMD directory
(plus the app data tree). The .fchk comes from a finished job (formchk) or a
user-supplied path.
"""
from __future__ import annotations

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

# Atomic numbers for computing N_occ (HOMO/LUMO orbital indices).
_ATOMIC_NUM = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9,
    "Ne": 10, "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16, "Cl": 17,
    "Ar": 18, "K": 19, "Ca": 20, "Sc": 21, "Ti": 22, "V": 23, "Cr": 24, "Mn": 25,
    "Fe": 26, "Co": 27, "Ni": 28, "Cu": 29, "Zn": 30, "Ga": 31, "Ge": 32, "As": 33,
    "Se": 34, "Br": 35, "Kr": 36, "Rb": 37, "Sr": 38, "I": 53, "Xe": 54,
}


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
    try:
        mol = load_molecule(job.get("molecule_id", ""))
        n = len(mol.atoms)
        n_elec = sum(_ATOMIC_NUM.get(a.element, 6) for a in mol.atoms) - mol.charge
        n_occ = max(1, n_elec // 2)  # closed-shell approximation
        subs = {
            "{atoms}": f"1-{n}",
            "{homo}": str(n_occ),
            "{lumo}": str(n_occ + 1),
        }
        for k, v in subs.items():
            input_lines = [l.replace(k, v) for l in input_lines]
    except Exception:
        pass
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
    vmd = s.get("vmd_path", "")
    if not vmd:
        raise HTTPException(400, "未配置 VMD 路径")
    vmd_dir = tool_dir(vmd)
    img = (vmd_dir / "aagd_plots" / run_id / name).resolve()
    # strict sandbox: only allow png/jpg/tga inside aagd_plots
    if not name.lower().endswith((".png", ".jpg", ".jpeg", ".tga")):
        raise HTTPException(400, "不支持的图像类型")
    if not is_within(img, vmd_dir / "aagd_plots"):
        raise HTTPException(403, "路径越界")
    if not img.exists():
        raise HTTPException(404, "图像尚未生成")
    return FileResponse(str(img))
