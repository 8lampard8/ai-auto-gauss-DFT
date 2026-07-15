"""Molecule importers.

Normalize every supported input into a :class:`Molecule`:
  - SMILES  (RDKit + ETKDG 3D embed + MMFF refine)
  - mol/mol2 (RDKit)
  - gjf     (custom parser: link0, route, charge/mult, cartesian atoms)
  - out/log (last "Standard orientation" + charge/multiplicity)
  - cdxml   (ChemDraw XML, best-effort)
  - image   (OSRA if installed, else the active OpenAI-compatible vision model)

The viewer prefers ``molblock`` (carries bonds); for gjf/out we emit ``xyz``
and let 3Dmol infer bonds from distances.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import tempfile
import uuid

from ..schemas import Atom, Bond, Molecule


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _sym_from_atomic_num(n: int) -> str:
    from rdkit import Chem

    return Chem.GetSymbol(int(n))


def _infer_multiplicity(mol) -> int:
    radicals = sum(a.GetNumRadicalElectrons() for a in mol.GetAtoms())
    return radicals + 1 if radicals > 0 else 1


def _atoms_to_xyz(atoms: list[Atom], charge: int, mult: int) -> str:
    lines = [str(len(atoms)), f"{charge} {mult}"]
    for a in atoms:
        lines.append(f"{a.element} {a.x:.6f} {a.y:.6f} {a.z:.6f}")
    return "\n".join(lines) + "\n"


def _new_id() -> str:
    return "mol-" + uuid.uuid4().hex[:10]


def _mol_to_molecule(mol, source: str, name: str = "", smiles: str = "",
                     route: str = "", title: str = "") -> Molecule:
    """Build a Molecule from an RDKit Mol that already has a conformer."""
    from rdkit import Chem

    charge = Chem.GetFormalCharge(mol)
    mult = _infer_multiplicity(mol)
    try:
        mb = Chem.MolToMolBlock(mol)
    except Exception:
        mb = ""
    atoms: list[Atom] = []
    if mol.GetNumConformers():
        conf = mol.GetConformer()
        for a in mol.GetAtoms():
            p = conf.GetAtomPosition(a.GetIdx())
            atoms.append(Atom(element=a.GetSymbol(), x=p.x, y=p.y, z=p.z))
    bonds = [
        Bond(a1=b.GetBeginAtomIdx(), a2=b.GetEndAtomIdx(),
             order=b.GetBondTypeAsDouble())
        for b in mol.GetBonds()
    ]
    smi = smiles or ""
    if not smi:
        try:
            smi = Chem.MolToSmiles(mol)
        except Exception:
            pass
    return Molecule(
        id=_new_id(),
        name=name or title or (smi or "molecule"),
        source=source,
        charge=charge,
        multiplicity=mult,
        atoms=atoms,
        bonds=bonds,
        smiles=smi,
        molblock=mb,
        route=route,
        title=title,
    )


# ---------------------------------------------------------------------------
# SMILES
# ---------------------------------------------------------------------------
def _diagnose_smiles(smi: str) -> str:
    """Return a human-readable diagnosis of why a SMILES failed to parse."""
    issues: list[str] = []
    op, cp = smi.count("("), smi.count(")")
    if op != cp:
        issues.append(f"括号不匹配('('{op} / ')'{cp})")
    digits: dict[str, int] = {}
    for c in smi:
        if c.isdigit():
            digits[c] = digits.get(c, 0) + 1
    bad = {d: n for d, n in digits.items() if n != 2}
    if bad:
        issues.append(
            "环闭合数字 " + ", ".join(f"'{d}' 出现 {n} 次(应为恰好 2 次)" for d, n in bad.items())
        )
    from rdkit import Chem

    m = Chem.MolFromSmiles(smi, sanitize=False)
    if m is None:
        issues.append("RDKit 语法解析失败(检查上述项或非法符号)")
    else:
        try:
            Chem.SanitizeMol(m, sanitizeOps=Chem.SanitizeFlags.SANITIZE_ALL)
        except Exception as e:
            issues.append(
                "芳香性/Kekulé 结构无法确定(常见于环大小错误或芳香原子 'c' 误用):"
                f"{type(e).__name__}"
            )
    return "; ".join(issues) if issues else "未知原因"


def _is_c60(mol) -> bool:
    """C60 fullerene: 60 carbon atoms, each 3-connected (no implicit H)."""
    if mol.GetNumAtoms() != 60:
        return False
    return all(a.GetSymbol() == "C" and a.GetTotalNumHs() == 0
               for a in mol.GetAtoms())


def _build_c60_molecule(name: str = "C60 fullerene") -> Molecule:
    """Build C60 from the exact truncated-icosahedron geometry.

    RDKit's distance-geometry embedder cannot place the spherical cage, so we
    generate the 60 vertices directly and add bonds by distance.
    """
    import math

    from rdkit import Chem

    phi = (1 + math.sqrt(5)) / 2

    def even_perms(a, b, c):
        return [(a, b, c), (b, c, a), (c, a, b)]

    verts: list[tuple[float, float, float]] = []
    for s2 in (1, -1):
        for s3 in (1, -1):
            verts += even_perms(0.0, float(s2), s3 * 3 * phi)
    for s1 in (1, -1):
        for s2 in (1, -1):
            for s3 in (1, -1):
                verts += even_perms(float(s1), s2 * (2 + phi), s3 * 2 * phi)
                verts += even_perms(s1 * phi, float(s2 * 2), s3 * (2 * phi + 1))
    verts = list(dict.fromkeys(verts))
    dmin = min(math.dist(verts[i], verts[j])
               for i in range(len(verts)) for j in range(i + 1, len(verts)))
    scale = 1.42 / dmin
    verts = [(x * scale, y * scale, z * scale) for x, y, z in verts]

    rw = Chem.RWMol()
    conf = Chem.Conformer(len(verts))
    for i, (x, y, z) in enumerate(verts):
        rw.AddAtom(Chem.Atom(6))
        conf.SetAtomPosition(i, (x, y, z))
    for i in range(len(verts)):
        for j in range(i + 1, len(verts)):
            if math.dist(verts[i], verts[j]) < 1.55:
                rw.AddBond(i, j, Chem.BondType.SINGLE)
    rw.AddConformer(conf, assignId=True)
    return _mol_to_molecule(rw.GetMol(), "smiles", name=name, smiles="C60")


def from_smiles(smi: str, name: str = "") -> Molecule:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        raise ValueError(f"无效 SMILES:{_diagnose_smiles(smi)}。原始:{smi[:80]}")
    # C60 fullerene: RDKit can't embed the spherical cage; use exact geometry.
    if _is_c60(mol):
        return _build_c60_molecule(name or "buckminsterfullerene (C60)")
    mol = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol, randomSeed=0xF00D) != 0:
        # fallbacks for strained / large-ring systems
        if AllChem.EmbedMolecule(mol, randomSeed=0xF00D, useRandomCoords=True) != 0:
            Chem.Compute2DCoords(mol)  # last resort: flat layout
    try:
        AllChem.MMFFOptimizeMolecule(mol, maxIters=300)
    except Exception:
        pass
    return _mol_to_molecule(mol, "smiles", name=name or smi, smiles=smi)


# ---------------------------------------------------------------------------
# mol / mol2
# ---------------------------------------------------------------------------
def from_molblock(text: str, name: str = "") -> Molecule:
    from rdkit import Chem

    mol = Chem.MolFromMolBlock(text)
    if mol is None:
        raise ValueError("无法解析 MOL/SDF")
    return _mol_to_molecule(mol, "mol", name=name)


def from_mol2(text: str, name: str = "") -> Molecule:
    from rdkit import Chem

    mol = Chem.MolFromMol2Block(text)
    if mol is None:
        raise ValueError("无法解析 MOL2")
    return _mol_to_molecule(mol, "mol2", name=name)


# ---------------------------------------------------------------------------
# gjf
# ---------------------------------------------------------------------------
def from_gjf(text: str, name: str = "") -> Molecule:
    lines = text.splitlines()
    n = len(lines)
    i = 0
    # locate route line(s)
    while i < n and not lines[i].lstrip().startswith("#"):
        i += 1
    route_lines: list[str] = []
    while i < n and lines[i].strip():
        route_lines.append(lines[i])
        i += 1
    route = " ".join(route_lines)
    while i < n and not lines[i].strip():
        i += 1
    title_lines: list[str] = []
    while i < n and lines[i].strip():
        title_lines.append(lines[i])
        i += 1
    title = " ".join(title_lines)
    while i < n and not lines[i].strip():
        i += 1
    charge, mult = 0, 1
    if i < n:
        cm = lines[i].split()
        if len(cm) >= 2:
            try:
                charge, mult = int(cm[0]), int(cm[1])
            except ValueError:
                pass
        i += 1
    atoms: list[Atom] = []
    while i < n:
        s = lines[i]
        if not s.strip():
            break
        toks = s.split()
        if len(toks) < 4:
            break
        t0 = toks[0]
        m = re.match(r"[A-Za-z]{1,2}", t0)
        if m:
            sym = m.group().capitalize()
        else:
            try:
                sym = _sym_from_atomic_num(int(t0))
            except ValueError:
                break
        try:
            x, y, z = map(float, toks[-3:])
        except ValueError:
            i += 1
            continue
        atoms.append(Atom(element=sym, x=x, y=y, z=z))
        i += 1
    if not atoms:
        raise ValueError("gjf 未解析到原子坐标(暂不支持纯 Z-matrix)")
    xyz = _atoms_to_xyz(atoms, charge, mult)
    return Molecule(
        id=_new_id(),
        name=name or title or "gjf_molecule",
        source="gjf",
        charge=charge,
        multiplicity=mult,
        atoms=atoms,
        bonds=[],
        molblock="",
        xyz=xyz,
        route=route,
        title=title,
    )


# ---------------------------------------------------------------------------
# Gaussian out / log
# ---------------------------------------------------------------------------
def from_gaussian_log(text: str, name: str = "") -> Molecule:
    occ = [m.start() for m in re.finditer(r"Standard orientation:")]
    if not occ:
        raise ValueError("未找到 Standard orientation(可能计算未完成或为输入文件)")
    sub = text[occ[-1]:]
    atoms: list[Atom] = []
    for line in sub.splitlines()[1:]:
        s = line.strip()
        if not s:
            if atoms:
                break
            continue
        if set(s) <= set("-"):
            if atoms:
                break
            continue
        toks = s.split()
        if len(toks) >= 6:
            try:
                an = int(toks[1])
                x, y, z = float(toks[3]), float(toks[4]), float(toks[5])
            except ValueError:
                continue  # header line
            atoms.append(Atom(element=_sym_from_atomic_num(an), x=x, y=y, z=z))
    if not atoms:
        raise ValueError("未解析到 Standard orientation 坐标")
    cm = re.search(r"Charge\s*=\s*(-?\d+)\s*Multiplicity\s*=\s*(\d+)", text)
    charge, mult = (int(cm.group(1)), int(cm.group(2))) if cm else (0, 1)
    # route
    rm = re.search(r"#\s*N?\s*\n?(.*?)\n\s*---", text, re.S)
    route = rm.group(1).strip() if rm else ""
    xyz = _atoms_to_xyz(atoms, charge, mult)
    return Molecule(
        id=_new_id(),
        name=name or "gaussian_log",
        source="out",
        charge=charge,
        multiplicity=mult,
        atoms=atoms,
        bonds=[],
        molblock="",
        xyz=xyz,
        route=route,
    )


# ---------------------------------------------------------------------------
# ChemDraw cdxml (best-effort)
# ---------------------------------------------------------------------------
def from_cdxml(text: str, name: str = "") -> Molecule:
    import lxml.etree as ET
    from rdkit import Chem

    root = ET.fromstring(text.encode("utf-8"))
    atom_ids: dict[str, int] = {}
    order: list[tuple[str, float, float, float]] = []
    for node in root.iter("n"):
        eid = node.get("id")
        el = node.get("Element")
        p = node.find("p")
        if p is not None:
            x = float(p.get("x") or 0)
            y = float(p.get("y") or 0)
            z = float(p.get("z") or 0)
        else:
            x = float(node.get("x") or 0)
            y = float(node.get("y") or 0)
            z = float(node.get("z") or 0)
        sym = _sym_from_atomic_num(int(el)) if el and el.isdigit() else "C"
        atom_ids[eid] = len(order)
        order.append((sym, x, y, z))
    bonds_spec: list[tuple[int, int, float]] = []
    for b in root.iter("b"):
        bi, ei = b.get("B"), b.get("E")
        if bi in atom_ids and ei in atom_ids:
            ordv = {"2": 2.0, "3": 3.0, "1.5": 1.5}.get(b.get("Order", "1"), 1.0)
            bonds_spec.append((atom_ids[bi], atom_ids[ei], ordv))
    if not order:
        raise ValueError("cdxml 未解析到原子")
    rw = Chem.RWMol()
    conf = Chem.Conformer(len(order))
    for i, (sym, x, y, z) in enumerate(order):
        rw.AddAtom(Chem.Atom(sym))
        conf.SetAtomPosition(i, (x, y, z))
    bt = {2.0: Chem.BondType.DOUBLE, 3.0: Chem.BondType.TRIPLE,
          1.5: Chem.BondType.AROMATIC, 1.0: Chem.BondType.SINGLE}
    for a1, a2, od in bonds_spec:
        try:
            rw.AddBond(a1, a2, bt.get(od, Chem.BondType.SINGLE))
        except Exception:
            pass
    rw.AddConformer(conf, assignId=True)
    mol = rw.GetMol()
    try:
        smi = Chem.MolToSmiles(mol)
    except Exception:
        smi = ""
    return _mol_to_molecule(mol, "cdxml", name=name, smiles=smi)


# ---------------------------------------------------------------------------
# image (OSRA or vision LLM)
# ---------------------------------------------------------------------------
def _extract_error(body: str) -> str:
    """Best-effort extraction of a provider error message from a JSON body."""
    try:
        d = json.loads(body)
    except Exception:
        return ""
    err = d.get("error", d)
    if isinstance(err, dict):
        return err.get("message") or err.get("code") or ""
    return str(err)


def _vision_smiles(provider: dict, b64: str, mime: str,
                   model: str | None = None) -> str:
    import httpx

    base = (provider.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    url = base + "/chat/completions"
    data_url = f"data:{mime or 'image/png'};base64,{b64}"
    mdl = (
        model
        or provider.get("default_model")
        or (provider["models"][0] if provider.get("models") else "gpt-4o-mini")
    )
    payload = {
        "model": mdl,
        "messages": [
            {"role": "system", "content": "你是化学结构识别助手。只输出该分子结构的 SMILES,不要任何解释或额外文字。无法识别时只输出 ERROR。"},
            {"role": "user", "content": [
                {"type": "text", "text": "识别图片中分子的 SMILES。"},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ],
        "temperature": 0.0,
        "max_tokens": 200,
    }
    headers = {"Authorization": f"Bearer {provider['api_key']}"}
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=60.0)
    except httpx.RequestError as e:
        raise ValueError(f"视觉模型网络请求失败:{e}")
    if r.status_code != 200:
        msg = _extract_error(r.text) or r.text[:300]
        raise ValueError(
            f"视觉模型({mdl})返回 {r.status_code}:{msg}。"
            "该模型可能不支持图片输入,请在「设置」中配置支持视觉的模型"
            "(如 GPT-4o / Claude / GLM-4V / Doubao-vision),或安装 OSRA,"
            "或改用 SMILES / 文件导入。"
        )
    try:
        out = r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        raise ValueError(f"视觉模型响应格式异常:{r.text[:200]}")
    out = out.strip().strip("`").strip()
    if not out or out.upper().startswith("ERROR"):
        return ""
    return out.split()[0]


def from_image(b64: str, mime: str, name: str, settings: dict,
               provider_id: str | None = None, model: str | None = None) -> Molecule:
    osra = shutil.which("osra")
    if osra:
        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            f.write(base64.b64decode(b64))
            f.flush()
            try:
                res = subprocess.run([osra, f.name], capture_output=True,
                                     text=True, timeout=40)
            except Exception as e:
                raise ValueError(f"OSRA 执行失败:{e}")
            smi = (res.stdout or "").strip().split()
            if smi:
                return from_smiles(smi[0], name or "image")
        raise ValueError("OSRA 未能从图片识别结构")
    # fallback: an OpenAI-compatible vision provider (explicit or active)
    pid = provider_id or settings.get("active_provider_id")
    prov = next((p for p in settings.get("providers", []) if p["id"] == pid), None)
    if prov and prov.get("kind") in ("openai", "custom") and prov.get("api_key"):
        smi = _vision_smiles(prov, b64, mime, model=model)
        if smi:
            return from_smiles(smi, name or "image")
        raise ValueError("视觉模型未能识别 SMILES(返回为空或 ERROR)")
    raise ValueError(
        "图片导入需要安装 OSRA,或在「设置」配置一个支持视觉的 OpenAI 兼容模型后重试"
    )


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------
def import_molecule(source: str, content: str, filename: str = "",
                    mime: str = "", name: str = "",
                    settings: dict | None = None,
                    provider_id: str | None = None,
                    model: str | None = None) -> Molecule:
    src = source.lower()
    nm = name or (filename.rsplit(".", 1)[0] if filename else "")
    if src == "smiles":
        return from_smiles(content.strip(), nm)
    if src == "mol":
        return from_molblock(content, nm)
    if src == "mol2":
        return from_mol2(content, nm)
    if src == "gjf":
        return from_gjf(content, nm)
    if src in ("out", "log"):
        return from_gaussian_log(content, nm)
    if src == "cdxml":
        return from_cdxml(content, nm)
    if src == "image":
        return from_image(content, mime or "image/png", nm, settings or {},
                          provider_id=provider_id, model=model)
    raise ValueError(f"不支持的来源:{source}")
