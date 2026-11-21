"""Structure-based molecular descriptors (RDKit).

Works for every molecule source in the app:

* ``molblock`` (SMILES / mol / mol2 / cdxml imports) -> bonds are known;
* ``xyz`` only (gjf / Gaussian-output imports) -> bonds are perceived with
  ``rdDetermineBonds`` (Hueckel/xTB-free connectivity + bond orders), falling
  back to connectivity-only when bond orders can't be assigned.

Descriptors are grouped (basic / drug-likeness / topology / 3D shape) for the
UI; ``full=True`` additionally returns every RDKit 2D descriptor (~200) for
machine-learning dataset export.
"""
from __future__ import annotations

import math
from typing import Any

from ..schemas import Molecule


# ---------------------------------------------------------------------------
# Molecule -> RDKit Mol
# ---------------------------------------------------------------------------
def _xyz_block(mol: Molecule) -> str:
    lines = [str(len(mol.atoms)), mol.name or "mol"]
    lines += [f"{a.element} {a.x:.6f} {a.y:.6f} {a.z:.6f}" for a in mol.atoms]
    return "\n".join(lines) + "\n"


def to_rdkit(mol: Molecule) -> tuple[Any, str, list[str]]:
    """Return ``(rdkit_mol_with_Hs, perception_method, warnings)``."""
    from rdkit import Chem

    warnings: list[str] = []
    if mol.molblock:
        m = Chem.MolFromMolBlock(mol.molblock, removeHs=False, sanitize=True)
        if m is not None:
            return m, "molblock", warnings
        warnings.append("MOL 块解析失败,改用其他来源。")

    if mol.atoms:
        from rdkit.Chem import rdDetermineBonds

        raw = Chem.MolFromXYZBlock(_xyz_block(mol))
        if raw is not None:
            m = Chem.Mol(raw)
            try:
                rdDetermineBonds.DetermineBonds(m, charge=int(mol.charge))
                Chem.SanitizeMol(m)
                return m, "xyz+bond-orders", warnings
            except Exception:
                m = Chem.Mol(raw)
                try:
                    rdDetermineBonds.DetermineConnectivity(m)
                    m.UpdatePropertyCache(strict=False)
                    Chem.GetSymmSSSR(m)
                    warnings.append("无法确定键级(可能为自由基/金属配合物),仅按距离判定连接性;"
                                    "依赖键级的描述符(芳香性、氢键供受体等)可能不准。")
                    return m, "xyz+connectivity", warnings
                except Exception:
                    pass

    if mol.smiles:
        m = Chem.MolFromSmiles(mol.smiles)
        if m is not None:
            warnings.append("无 3D 坐标,仅计算 2D 描述符。")
            return Chem.AddHs(m), "smiles", warnings

    raise ValueError("无法从该分子构建 RDKit 结构(缺少 molblock / 坐标 / SMILES)")


def _has_3d(m) -> bool:
    if not m.GetNumConformers():
        return False
    conf = m.GetConformer()
    if not conf.Is3D():
        return False
    zs = [conf.GetAtomPosition(i).z for i in range(m.GetNumAtoms())]
    return (max(zs) - min(zs)) > 1e-3 if zs else False


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _safe(fn, *args, **kw):
    try:
        v = fn(*args, **kw)
    except Exception:
        return None
    if hasattr(v, "item") and not isinstance(v, (list, tuple, dict, str)):
        try:
            v = v.item()          # numpy scalar -> Python scalar (JSON-safe)
        except Exception:
            pass
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _quiet(fn, *args, **kw):
    """Run an RDKit call with warnings muted (InChI is chatty on stderr)."""
    from rdkit import RDLogger

    RDLogger.DisableLog("rdApp.*")
    try:
        return _safe(fn, *args, **kw)
    finally:
        RDLogger.EnableLog("rdApp.*")


def _item(key: str, label: str, value: Any, unit: str = "", nd: int = 4, hint: str = "") -> dict:
    if isinstance(value, float):
        value = round(value, nd)
    d = {"key": key, "label": label, "value": value, "unit": unit}
    if hint:
        d["hint"] = hint
    return d


def _wiener(m) -> int | None:
    from rdkit import Chem

    if m.GetNumAtoms() > 2000:
        return None
    dm = Chem.GetDistanceMatrix(m)
    n = len(dm)
    total = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            d = dm[i][j]
            if d < 1e6:  # disconnected fragments -> huge value
                total += d
    return int(total)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def rdkit_descriptors(mol: Molecule, full: bool = False) -> dict[str, Any]:
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski, QED, rdMolDescriptors as rd

    mh, method, warnings = to_rdkit(mol)
    try:
        m = Chem.RemoveHs(mh, sanitize=False)
        m.UpdatePropertyCache(strict=False)
        Chem.GetSymmSSSR(m)
    except Exception:
        m = mh
    sanitized = method in ("molblock", "xyz+bond-orders", "smiles")

    smiles = _safe(Chem.MolToSmiles, m) or mol.smiles
    inchi = _quiet(Chem.MolToInchi, m) if sanitized else None
    inchikey = _quiet(Chem.MolToInchiKey, m) if sanitized else None
    n_rad = sum(a.GetNumRadicalElectrons() for a in mh.GetAtoms())

    groups: list[dict] = []
    basic = [
        _item("formula", "分子式", _safe(rd.CalcMolFormula, mh)),
        _item("canonical_smiles", "规范 SMILES", smiles),
        _item("inchikey", "InChIKey", inchikey),
        _item("inchi", "InChI", inchi),
        _item("mol_wt", "分子量", _safe(Descriptors.MolWt, mh), "g/mol", 3),
        _item("exact_mass", "精确质量 (单同位素)", _safe(Descriptors.ExactMolWt, mh), "Da", 5),
        _item("n_atoms", "原子总数 (含 H)", mh.GetNumAtoms()),
        _item("n_heavy_atoms", "重原子数", _safe(Lipinski.HeavyAtomCount, m)),
        _item("n_heteroatoms", "杂原子数", _safe(rd.CalcNumHeteroatoms, m)),
        _item("formal_charge", "形式电荷", Chem.GetFormalCharge(mh)),
        _item("n_valence_electrons", "价电子数", _safe(Descriptors.NumValenceElectrons, mh)),
        _item("n_radical_electrons", "自由基电子数", n_rad),
        _item("n_bonds", "化学键数 (含 H)", mh.GetNumBonds()),
        _item("n_stereocenters", "手性中心数",
              len(_safe(Chem.FindMolChiralCenters, m, includeUnassigned=True,
                        useLegacyImplementation=False) or []) if sanitized else None),
    ]
    groups.append({"id": "basic", "label": "基本信息", "items": basic})

    if sanitized:
        mw = _safe(Descriptors.MolWt, m) or 0
        logp = _safe(Crippen.MolLogP, m)
        hbd = _safe(rd.CalcNumHBD, m)
        hba = _safe(rd.CalcNumHBA, m)
        rotb = _safe(rd.CalcNumRotatableBonds, m)
        tpsa = _safe(rd.CalcTPSA, m)
        lip_viol = sum([
            mw > 500,
            (logp or 0) > 5,
            (hbd or 0) > 5,
            (hba or 0) > 10,
        ])
        drug = [
            _item("logp", "脂水分配系数 logP (Crippen)", logp, "", 3),
            _item("mr", "摩尔折射率 MR (Crippen)", _safe(Crippen.MolMR, m), "", 3),
            _item("tpsa", "拓扑极性表面积 TPSA", tpsa, "Å²", 2),
            _item("labute_asa", "Labute 近似表面积", _safe(rd.CalcLabuteASA, m), "Å²", 2),
            _item("hbd", "氢键供体数", hbd),
            _item("hba", "氢键受体数", hba),
            _item("rot_bonds", "可旋转键数", rotb),
            _item("n_rings", "环数", _safe(rd.CalcNumRings, m)),
            _item("n_aromatic_rings", "芳香环数", _safe(rd.CalcNumAromaticRings, m)),
            _item("fraction_csp3", "sp³ 碳比例 Fsp3", _safe(rd.CalcFractionCSP3, m), "", 3),
            _item("qed", "类药性 QED", _safe(QED.qed, m), "", 3, "0~1,越大越类药"),
            _item("lipinski_violations", "Lipinski 五规则违反数", lip_viol, "", 0, "≤1 通常视为可口服"),
            _item("veber_pass", "Veber 规则", bool((rotb or 0) <= 10 and (tpsa or 0) <= 140)),
            _item("max_partial_charge", "最大 Gasteiger 电荷", _safe(Descriptors.MaxPartialCharge, m), "e", 4),
            _item("min_partial_charge", "最小 Gasteiger 电荷", _safe(Descriptors.MinPartialCharge, m), "e", 4),
        ]
        groups.append({"id": "druglike", "label": "理化性质 / 类药性", "items": drug})

    topo = [
        _item("bertz_ct", "Bertz 复杂度 BertzCT", _safe(Descriptors.BertzCT, m), "", 2),
        _item("balaban_j", "Balaban J", _safe(Descriptors.BalabanJ, m), "", 4),
        _item("wiener", "Wiener 指数", _safe(_wiener, m)),
        _item("hall_kier_alpha", "Hall-Kier α", _safe(rd.CalcHallKierAlpha, m), "", 4),
        _item("kappa1", "κ1 形状指数", _safe(rd.CalcKappa1, m), "", 4),
        _item("kappa2", "κ2 形状指数", _safe(rd.CalcKappa2, m), "", 4),
        _item("kappa3", "κ3 形状指数", _safe(rd.CalcKappa3, m), "", 4),
        _item("chi0v", "χ0v 连接性指数", _safe(rd.CalcChi0v, m), "", 4),
        _item("chi1v", "χ1v 连接性指数", _safe(rd.CalcChi1v, m), "", 4),
        _item("chi2v", "χ2v 连接性指数", _safe(rd.CalcChi2v, m), "", 4),
    ]
    groups.append({"id": "topology", "label": "拓扑指数", "items": [i for i in topo if i["value"] is not None]})

    if _has_3d(mh):
        from rdkit.Chem import AllChem

        shape = [
            _item("radius_of_gyration", "回转半径 Rg", _safe(rd.CalcRadiusOfGyration, mh), "Å", 4),
            _item("pmi1", "主惯量矩 I1", _safe(rd.CalcPMI1, mh), "amu·Å²", 3),
            _item("pmi2", "主惯量矩 I2", _safe(rd.CalcPMI2, mh), "amu·Å²", 3),
            _item("pmi3", "主惯量矩 I3", _safe(rd.CalcPMI3, mh), "amu·Å²", 3),
            _item("npr1", "归一化惯量比 NPR1", _safe(rd.CalcNPR1, mh), "", 4, "NPR1/NPR2 三角图:棒状/盘状/球状"),
            _item("npr2", "归一化惯量比 NPR2", _safe(rd.CalcNPR2, mh), "", 4),
            _item("asphericity", "非球度", _safe(rd.CalcAsphericity, mh), "", 4),
            _item("eccentricity", "偏心率", _safe(rd.CalcEccentricity, mh), "", 4),
            _item("spherocity", "球形度指数", _safe(rd.CalcSpherocityIndex, mh), "", 4),
            _item("inertial_shape_factor", "惯量形状因子", _safe(rd.CalcInertialShapeFactor, mh), "", 6),
            _item("pbf", "最佳拟合平面偏离 PBF", _safe(rd.CalcPBF, mh), "Å", 4, "0 表示完全平面"),
            _item("vdw_volume", "分子体积 (vdW, 网格法)",
                  _safe(AllChem.ComputeMolVolume, mh, gridSpacing=0.2), "Å³", 2),
        ]
        groups.append({"id": "shape3d", "label": "3D 几何形状", "items": [i for i in shape if i["value"] is not None]})
    else:
        warnings.append("无 3D 构象,跳过 3D 形状描述符。")

    flat: dict[str, Any] = {}
    for g in groups:
        for it in g["items"]:
            flat[it["key"]] = it["value"]

    result: dict[str, Any] = {
        "molecule_id": mol.id,
        "name": mol.name,
        "source": mol.source,
        "perception": method,
        "groups": groups,
        "warnings": warnings,
        "flat": flat,
    }
    if full:
        result["all"] = all_rdkit_descriptors(m)
    return result


def all_rdkit_descriptors(m) -> dict[str, float | int | None]:
    """Every RDKit 2D descriptor (``Descriptors._descList``), NaN -> None."""
    from rdkit.Chem import Descriptors

    out: dict[str, float | int | None] = {}
    for name, fn in Descriptors._descList:
        v = _safe(fn, m)
        if isinstance(v, float):
            v = round(v, 6)
        out[name] = v
    return out


def brief_summary(mol: Molecule) -> str:
    """One-line descriptor summary for the chat system prompt."""
    try:
        d = rdkit_descriptors(mol)["flat"]
    except Exception:
        return ""
    parts = []
    for k, label, unit in [("formula", "分子式", ""), ("mol_wt", "MW", " g/mol"),
                           ("logp", "logP", ""), ("tpsa", "TPSA", " Å²"),
                           ("hbd", "HBD", ""), ("hba", "HBA", ""),
                           ("rot_bonds", "可旋转键", ""), ("qed", "QED", "")]:
        v = d.get(k)
        if v is not None:
            parts.append(f"{label}={v}{unit}")
    return ", ".join(parts)
