"""Rule-based method recommender.

Maps {task, solvent, accuracy, charge, multiplicity} to a :class:`MethodSpec`
(functional / basis / route / dispersion / SCRF). Heuristics distilled from
the sobko knowledge base and common Gaussian practice; the LLM can override
any field when the user asks for something specific.
"""
from __future__ import annotations

from ..schemas import MethodSpec

# Functionals that already include dispersion -> no separate em= keyword.
_BUILTIN_DISP = {"wB97XD", "wB97X-D", "M06", "M06-2X", "M06-L", "MN15", "M11"}


def recommend(
    task: str = "optfreq",
    solvent: str = "",
    accuracy: str = "standard",
    charge: int = 0,
    multiplicity: int | None = None,
) -> MethodSpec:
    # --- functional / basis by accuracy tier -------------------------------
    if accuracy == "fast":
        functional, basis, label = "B3LYP", "def2-SVP", "B3LYP-D3(BJ)/def2-SVP"
    elif accuracy == "high":
        functional, basis, label = "B2PLYP", "def2-TZVPP", "B2PLYP-D3(BJ)/def2-TZVPP"
    else:
        functional, basis, label = "B3LYP", "def2-TZVP", "B3LYP-D3(BJ)/def2-TZVP"

    # --- route by task -----------------------------------------------------
    route = "opt freq"
    if task == "opt":
        route = "opt"
    elif task == "freq":
        route = "freq"
    elif task == "optfreq":
        route = "opt freq"
    elif task == "sp":
        route = ""
    elif task == "ts":
        route = "opt=(ts,calcfc,noeigentest) freq"
    elif task == "qst2":
        route = "opt=qst2 freq"
    elif task == "irc":
        route = "irc"
    elif task == "scan":
        route = "opt=modredundant"
    elif task == "nmr":
        route = "nmr=giao"
    elif task == "tddft":
        if accuracy == "high":
            functional, basis, label = "CAM-B3LYP", "def2-TZVP", "CAM-B3LYP/def2-TZVP"
        else:
            functional, basis, label = "PBE0", "def2-TZVP", "PBE0/def2-TZVP"
        route = "td(nstates=20)"

    # --- dispersion --------------------------------------------------------
    dispersion = "" if functional in _BUILTIN_DISP else "em=gd3bj"

    # --- SCRF --------------------------------------------------------------
    scrf = ""
    if solvent:
        # PCM (IEFPCM) is the G16 default and the standard choice for
        # geometry / properties in solution; SMD is preferred for ΔG_solv.
        scrf = f"scrf=(pcm,solvent={solvent})"

    mult = multiplicity if multiplicity is not None else 1

    explanation = (
        f"推荐方法:{label}。"
        + (f" 溶剂 {solvent} 使用隐式溶剂模型 {scrf}。" if solvent else " 气相。")
        + f" 多重度 {mult}、电荷 {charge}。"
        + (" " + _task_note(task) if _task_note(task) else "")
    )

    return MethodSpec(
        functional=functional,
        basis=basis,
        route=route,
        dispersion=dispersion,
        scrf=scrf,
        charge=charge,
        multiplicity=mult,
        label=label,
        explanation=explanation,
    )


def _task_note(task: str) -> str:
    return {
        "ts": "过渡态:务必做 freq 验证唯一虚频。",
        "qst2": "QST2 需提供反应物与产物两套结构。",
        "tddft": "激发态:TDDFT,如含电荷转移可换 ωB97XD。",
        "irc": "IRC 需以过渡态结构为起点。",
        "nmr": "NMR 建议在优化后几何上做 GIAO。",
    }.get(task, "")
