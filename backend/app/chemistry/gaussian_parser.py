"""Gaussian output (.log/.out) parser -> quantum-chemical descriptors.

Pure-text parsing (no cclib dependency) of the quantities most commonly used
as DFT descriptors in QSAR / reactivity / materials studies:

* SCF energy, <S**2>, basis size, charge / multiplicity, route, stoichiometry
* frontier orbitals (HOMO / LUMO / gap, HOMO-1, LUMO+1; alpha + beta)
* conceptual-DFT global reactivity indices (Koopmans approximation)
* dipole moment, (hyper)polarizability
* thermochemistry (ZPE, H, G, thermal corrections, imaginary frequencies)
* TD-DFT excited states
* atomic charges: Mulliken / APT / Hirshfeld / CM5 / NPA (+ spin densities)

All parsers take the *last* occurrence of a block, so optimisation and
multi-step (``--Link1--``) outputs report the final geometry's values.
"""
from __future__ import annotations

import math
import re
from typing import Any

HARTREE_TO_EV = 27.211386245988
HARTREE_TO_KCAL = 627.5094740631
BOHR3_TO_ANG3 = 0.14818471147216278

_NUM = r"-?\d+\.\d+"
_NUM_RE = re.compile(_NUM)


def _f(s: str) -> float:
    return float(s.replace("D", "E").replace("d", "e"))


def _r(x: float | None, nd: int = 6) -> float | None:
    return None if x is None else round(x, nd)


# ---------------------------------------------------------------------------
# termination / error helpers (shared by the runners)
# ---------------------------------------------------------------------------
def terminated_normally(text: str) -> bool:
    """True only if *every* job step ended with Normal termination.

    A multi-step job (``--Link1--``, e.g. opt + freq) prints one
    "Normal termination" per step; a crash in a later step leaves an
    "Error termination" or simply stops after "Proceeding to internal job
    step". Checking ``"Normal termination" in text`` alone would mark those
    as successful.
    """
    t = text or ""
    last_ok = t.rfind("Normal termination of Gaussian")
    if last_ok < 0:
        return False
    if "Error termination" in t:
        return False
    last_step = t.rfind("Proceeding to internal job step")
    return last_ok > last_step


def is_link0_crash(text: str) -> bool:
    """G09W exits right after the SMP line, before parsing the route section."""
    t = text or ""
    smp = re.search(r"Will use up to\s+\d+\s+processors", t)
    if not smp:
        return False
    after = t[smp.end():]
    return "#" not in after and "Error termination" not in after


def extract_gaussian_error(text: str, rc: int | None) -> str:
    """Pull a concise, actionable reason out of a Gaussian log on failure."""
    t = text or ""
    if is_link0_crash(t):
        return (f"exit={rc};Gaussian 在解析 route 前退出(通常 %mem 过大或 "
                "%nprocshared 超出许可核数)。建议 %mem≤1000MB、%nprocshared=1 重试。")
    for pat, hint in [
        (r"Insufficient memory|Out of memory|malloc failed|not enough memory|galloc:\s+could not allocate",
         "内存不足:请减小 %mem / 换更小基组 / 减小体系(32 位 G09W 内存上限约 1.5GB)。"),
        (r"NTrErr|too many (basis functions|primitives)|maximum number of primitive",
         "基函数过多:请换小基组(如 6-31G*)或减少原子。"),
        (r"QPErr|A syntax error was detected in the input",
         "输入语法错误:检查 route 关键字、电荷多重度行、坐标格式。"),
        (r"The combination of multiplicity\s+\d+\s+and\s+\d+\s+electrons is impossible",
         "电荷/多重度与电子数不匹配:检查电荷与多重度。"),
        (r"Convergence failure -- run terminated",
         "SCF 不收敛:可尝试 scf=(xqc,maxcycle=512)、更好的初猜或调整几何。"),
        (r"Number of steps exceeded",
         "几何优化步数用尽:可用 opt=(maxcycles=200) 并从最后结构续算。"),
        (r"FileIO operation on non-existent file",
         "读取文件失败:检查 %chk / %oldchk 与 guess=read / geom=check 是否匹配。"),
        (r"Erroneous write|No space left on device|write error",
         "磁盘写入失败:检查 GAUSS_SCRDIR 所在磁盘剩余空间。"),
        (r"wsystem|No executable for file|No such file.*\.exe",
         "Gaussian 子程序(link)启动失败:检查 GAUSS_EXEDIR 与安装完整性。"),
    ]:
        if re.search(pat, t, re.I):
            return f"exit={rc};{hint}"
    m = re.search(r"forrtl: severe \((\d+)\)", t)
    if m:
        return (f"exit={rc};Fortran 运行时错误(severe {m.group(1)}),"
                "常见于内存/磁盘不足或体系过大。")
    m = re.search(r"Error termination via Lnk\w+ in (\S+?)(?:\.exe)?\s+at", t) or \
        re.search(r"Error termination via Lnk\w+ in (\S+)", t)
    if m:
        link = m.group(1)
        idx = t.rfind("Error termination")
        ctx = [ln.strip() for ln in t[max(0, idx - 300):idx].splitlines() if ln.strip()]
        tail = " | ".join(ctx[-3:])[:200]
        return f"exit={rc};Gaussian 在 {link} 失败{(': ' + tail) if tail else ''}。"
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    tail = lines[-1][:120] if lines else "(空日志)"
    return f"exit={rc};未见 Normal termination。日志末尾:{tail}"


# ---------------------------------------------------------------------------
# individual block parsers
# ---------------------------------------------------------------------------
def _route(text: str) -> str:
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.match(r"^\s#", ln):
            out = [ln.strip()]
            for nxt in lines[i + 1:i + 8]:
                if re.match(r"^\s*-{5,}\s*$", nxt):
                    break
                out.append(nxt.strip())
            return "".join(out)
    return ""


def _last(pattern: str, text: str, flags: int = 0):
    last = None
    for last in re.finditer(pattern, text, flags):
        pass
    return last


def _orbitals(text: str) -> dict[str, list[float]]:
    """Last block of orbital eigenvalues (Hartree)."""
    blocks: list[dict[str, list[float]]] = []
    cur: dict[str, list[float]] | None = None
    prev_was_eig = False
    pat = re.compile(r"^\s*(Alpha|Beta)\s+(occ|virt)\.\s+eigenvalues\s+--(.*)$")
    for ln in text.splitlines():
        m = pat.match(ln)
        if m:
            spin, kind, rest = m.group(1).lower(), m.group(2), m.group(3)
            if not prev_was_eig and spin == "alpha" and kind == "occ":
                cur = {"alpha_occ": [], "alpha_virt": [], "beta_occ": [], "beta_virt": []}
                blocks.append(cur)
            if cur is not None:
                cur[f"{spin}_{kind}"].extend(float(x) for x in _NUM_RE.findall(rest))
            prev_was_eig = True
        else:
            # The "The electronic state is ..." / "Condensed to atoms" lines end a block.
            if prev_was_eig and ln.strip() and not ln.lstrip().startswith(("Alpha", "Beta")):
                prev_was_eig = False
    return blocks[-1] if blocks else {}


def _dipole(text: str) -> dict[str, float] | None:
    m = _last(
        r"Dipole moment \(field-independent basis, Debye\):\s*\n\s*"
        rf"X=\s*({_NUM})\s+Y=\s*({_NUM})\s+Z=\s*({_NUM})\s+Tot=\s*({_NUM})",
        text,
    )
    if not m:
        return None
    x, y, z, tot = (float(m.group(i)) for i in range(1, 5))
    return {"x": x, "y": y, "z": z, "total": tot}


def _polarizability(text: str) -> dict[str, float] | None:
    """Isotropic / anisotropic polarizability in Bohr^3 (a.u.)."""
    # G16 block: "Dipole polarizability, Alpha (input orientation)." with iso/aniso in au
    m = _last(r"Dipole polarizability, Alpha \(input orientation\)\.(.*?)(?:\n\s*\n|\Z)",
              text, re.S)
    if m:
        blk = m.group(1)
        iso = re.search(r"^\s*iso\s+(\S+)", blk, re.M)
        aniso = re.search(r"^\s*aniso\s+(\S+)", blk, re.M)
        if iso:
            try:
                out = {"iso": _f(iso.group(1))}
                if aniso:
                    out["aniso"] = _f(aniso.group(1))
                return out
            except ValueError:
                pass
    m = _last(r"Exact polarizability:\s*(.*)", text)
    if m:
        vals = [float(v) for v in _NUM_RE.findall(m.group(1))]
        if len(vals) >= 6:
            xx, xy, yy, xz, yz, zz = vals[:6]
            iso = (xx + yy + zz) / 3.0
            aniso = math.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2
                                     + 6 * (xy ** 2 + xz ** 2 + yz ** 2)))
            return {"iso": iso, "aniso": aniso, "xx": xx, "yy": yy, "zz": zz}
    m = _last(rf"Isotropic polarizability for W=\s*{_NUM}\s+({_NUM})\s+Bohr", text)
    if m:
        return {"iso": float(m.group(1))}
    return None


def _thermo(text: str) -> dict[str, float]:
    keys = {
        "zpe": r"Zero-point correction=\s*(" + _NUM + ")",
        "corr_energy": r"Thermal correction to Energy=\s*(" + _NUM + ")",
        "corr_enthalpy": r"Thermal correction to Enthalpy=\s*(" + _NUM + ")",
        "corr_gibbs": r"Thermal correction to Gibbs Free Energy=\s*(" + _NUM + ")",
        "e_zpe": r"Sum of electronic and zero-point Energies=\s*(" + _NUM + ")",
        "e_thermal": r"Sum of electronic and thermal Energies=\s*(" + _NUM + ")",
        "enthalpy": r"Sum of electronic and thermal Enthalpies=\s*(" + _NUM + ")",
        "gibbs": r"Sum of electronic and thermal Free Energies=\s*(" + _NUM + ")",
    }
    out: dict[str, float] = {}
    for k, pat in keys.items():
        m = _last(pat, text)
        if m:
            out[k] = float(m.group(1))
    m = _last(rf"Temperature\s+({_NUM})\s+Kelvin\.\s+Pressure\s+({_NUM})\s+Atm", text)
    if m:
        out["temperature"] = float(m.group(1))
        out["pressure"] = float(m.group(2))
    return out


def _frequencies(text: str) -> list[float]:
    """Harmonic frequencies (cm^-1) of the *last* frequency calculation."""
    idx = text.rfind("Harmonic frequencies (cm**-1)")
    if idx < 0:
        return []
    sub = text[idx:]
    end = sub.find("- Thermochemistry -")
    if end > 0:
        sub = sub[:end]
    freqs: list[float] = []
    for m in re.finditer(r"^\s*Frequencies --(.*)$", sub, re.M):
        freqs.extend(float(v) for v in _NUM_RE.findall(m.group(1)))
    return freqs


def _excited_states(text: str) -> list[dict[str, Any]]:
    pat = re.compile(
        r"Excited State\s+(\d+):\s+(\S+)\s+(" + _NUM + r")\s+eV\s+(" + _NUM + r")\s+nm\s+"
        r"f=(" + _NUM + r")(?:\s+<S\*\*2>=(" + _NUM + r"))?"
    )
    states: dict[int, dict[str, Any]] = {}
    for m in pat.finditer(text):
        n = int(m.group(1))
        states[n] = {          # later blocks (opt steps) overwrite earlier ones
            "state": n,
            "symmetry": m.group(2),
            "energy_ev": float(m.group(3)),
            "wavelength_nm": float(m.group(4)),
            "f": float(m.group(5)),
            "s2": float(m.group(6)) if m.group(6) else None,
        }
    return [states[k] for k in sorted(states)]


_ATOM_ROW = re.compile(r"^\s*(\d+)\s+([A-Z][a-z]?|X|Bq)\s+(-?\d+\.\d+)(?:\s+(-?\d+\.\d+))?")


def _charge_block(text: str, header_re: str) -> tuple[list[dict], bool]:
    """Generic "  idx  El  q  [spin]" table after the last ``header_re``."""
    m = _last(header_re, text, re.M)
    if not m:
        return [], False
    rows: list[dict] = []
    has_spin = "spin" in m.group(0).lower()
    for ln in text[m.end():].splitlines()[1:]:
        s = ln.strip()
        if not s:
            continue
        if re.fullmatch(r"[\d\s]+", s) and not rows:  # column-number header "1  2"
            continue
        r = _ATOM_ROW.match(ln)
        if not r:
            break
        row = {"index": int(r.group(1)), "element": r.group(2), "charge": float(r.group(3))}
        if has_spin and r.group(4) is not None:
            row["spin"] = float(r.group(4))
        rows.append(row)
    return rows, has_spin


def _hirshfeld(text: str) -> list[dict]:
    m = _last(r"Hirshfeld (?:charges, spin densities, dipoles, and CM5 charges|spin densities, charges and dipoles).*$",
              text, re.M)
    if not m:
        return []
    has_cm5 = "cm5" in m.group(0).lower()
    rows: list[dict] = []
    lines = text[m.end():].splitlines()[1:]
    for ln in lines:
        if "Q-H" in ln:
            continue
        toks = ln.split()
        if len(toks) >= (8 if has_cm5 else 4) and toks[0].isdigit():
            try:
                row: dict[str, Any] = {
                    "index": int(toks[0]), "element": toks[1],
                    "hirshfeld": float(toks[2]), "hirshfeld_spin": float(toks[3]),
                }
                if has_cm5 and len(toks) >= 8:
                    row["cm5"] = float(toks[7])
                rows.append(row)
            except ValueError:
                break
        elif rows:
            break
    return rows


def _npa(text: str) -> list[dict]:
    occ = [m.end() for m in re.finditer(r"Summary of Natural Population Analysis:", text)]
    if not occ:
        return []
    open_shell = "Alpha spin orbitals" in text[occ[0]:]
    start = occ[-3] if (open_shell and len(occ) >= 3) else occ[-1]
    rows: list[dict] = []
    for ln in text[start:].splitlines():
        if ln.strip().startswith("====") and rows:
            break
        m = re.match(r"^\s*([A-Z][a-z]?)\s+(\d+)\s+(-?\d+\.\d+)\s+", ln)
        if m:
            rows.append({"index": int(m.group(2)), "element": m.group(1),
                         "npa": float(m.group(3))})
    return rows


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def parse_gaussian_log(text: str) -> dict[str, Any]:
    """Parse a Gaussian output into a raw (un-grouped) result dict."""
    t = text or ""
    res: dict[str, Any] = {}

    m = _last(r"Gaussian (\d\d):\s+(\S+)", t)
    res["program"] = f"Gaussian {m.group(1)} {m.group(2)}" if m else ""
    res["route"] = _route(t)
    m = _last(r"Stoichiometry\s+(\S+)", t)
    res["stoichiometry"] = m.group(1) if m else ""
    m = _last(r"Charge\s*=\s*(-?\d+)\s+Multiplicity\s*=\s*(\d+)", t)
    res["charge"], res["multiplicity"] = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    m = _last(r"NBasis=\s*(\d+)", t) or _last(r"(\d+)\s+basis functions,", t)
    res["nbasis"] = int(m.group(1)) if m else None
    m = _last(r"(\d+)\s+alpha electrons\s+(\d+)\s+beta electrons", t)
    res["n_alpha"], res["n_beta"] = (int(m.group(1)), int(m.group(2))) if m else (None, None)

    m = _last(rf"SCF Done:\s+E\((\S+)\)\s+=\s+({_NUM})", t)
    res["scf_method"] = m.group(1) if m else ""
    res["scf_energy"] = float(m.group(2)) if m else None
    m = _last(r"Total Energy, E\((?:TD-HF/TD-DFT|CIS)\)\s*=\s*(" + _NUM + ")", t)
    res["excited_total_energy"] = float(m.group(1)) if m else None
    m = _last(rf"S\*\*2 before annihilation\s+({_NUM}),\s+after\s+({_NUM})", t)
    if m:
        res["s2"], res["s2_after"] = float(m.group(1)), float(m.group(2))
    else:
        m = _last(rf"<S\*\*2>=\s*({_NUM})", t)
        res["s2"], res["s2_after"] = (float(m.group(1)) if m else None), None

    res["orbitals"] = _orbitals(t)
    res["dipole"] = _dipole(t)
    res["polarizability"] = _polarizability(t)
    res["thermo"] = _thermo(t)
    res["frequencies"] = _frequencies(t)
    res["excited_states"] = _excited_states(t)

    mull, mull_spin = _charge_block(
        t, r"^[ \t]*Mulliken (?:atomic )?charges(?: and spin densities)?:[ \t\r]*$")
    apt, _ = _charge_block(t, r"^[ \t]*APT (?:atomic )?charges:[ \t\r]*$")
    res["charges"] = {"mulliken": mull, "apt": apt, "hirshfeld": _hirshfeld(t), "npa": _npa(t)}
    res["has_spin"] = mull_spin

    res["normal_termination"] = terminated_normally(t)
    res["n_normal_termination"] = t.count("Normal termination of Gaussian")
    res["error_termination"] = "Error termination" in t
    is_opt = "Berny optimization" in t or bool(re.search(r"\bopt\b", res["route"], re.I))
    res["optimization_converged"] = (
        ("Optimization completed" in t or "Stationary point found" in t) if is_opt else None
    )
    m = _last(r"Elapsed time:\s+(\d+) days\s+(\d+) hours\s+(\d+) minutes\s+(" + _NUM + ")", t)
    if m:
        d, h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))
        res["elapsed_s"] = d * 86400 + h * 3600 + mi * 60 + s
    return res


def frontier(orbs: dict[str, list[float]]) -> dict[str, float | None]:
    """HOMO/LUMO (eV). For open-shell systems use the highest SOMO / lowest virtual."""
    a_occ, a_virt = orbs.get("alpha_occ") or [], orbs.get("alpha_virt") or []
    b_occ, b_virt = orbs.get("beta_occ") or [], orbs.get("beta_virt") or []
    occ = a_occ + b_occ
    virt = a_virt + b_virt
    if not occ:
        return {}
    homo = max(occ)
    lumo = min(virt) if virt else None
    occ_sorted = sorted(set(occ), reverse=True)
    virt_sorted = sorted(set(virt))
    out = {
        "homo": homo * HARTREE_TO_EV,
        "lumo": lumo * HARTREE_TO_EV if lumo is not None else None,
        "homo_1": occ_sorted[1] * HARTREE_TO_EV if len(occ_sorted) > 1 else None,
        "lumo_1": virt_sorted[1] * HARTREE_TO_EV if len(virt_sorted) > 1 else None,
        "alpha_homo": max(a_occ) * HARTREE_TO_EV if a_occ else None,
        "alpha_lumo": min(a_virt) * HARTREE_TO_EV if a_virt else None,
        "beta_homo": max(b_occ) * HARTREE_TO_EV if b_occ else None,
        "beta_lumo": min(b_virt) * HARTREE_TO_EV if b_virt else None,
    }
    out["gap"] = (out["lumo"] - out["homo"]) if out["lumo"] is not None else None
    return out


def conceptual_dft(homo_ev: float | None, lumo_ev: float | None) -> dict[str, float]:
    """Global reactivity indices from frontier orbitals (Koopmans' theorem).

    I = -E_HOMO, A = -E_LUMO, chi = (I+A)/2, mu = -chi, eta = (I-A)/2,
    S = 1/(2 eta), omega = mu^2/(2 eta) (Parr 1999),
    omega- = (3I+A)^2 / (16(I-A)), omega+ = (I+3A)^2 / (16(I-A)) (Gazquez 2007).
    """
    if homo_ev is None or lumo_ev is None:
        return {}
    ip, ea = -homo_ev, -lumo_ev
    chi = (ip + ea) / 2
    eta = (ip - ea) / 2
    out = {"ip": ip, "ea": ea, "electronegativity": chi, "chemical_potential": -chi,
           "hardness": eta}
    if eta > 1e-8:
        out["softness"] = 1 / (2 * eta)
        out["electrophilicity"] = chi ** 2 / (2 * eta)
        out["electrodonating"] = (3 * ip + ea) ** 2 / (16 * (ip - ea))
        out["electroaccepting"] = (ip + 3 * ea) ** 2 / (16 * (ip - ea))
    return out


def _merge_charges(ch: dict[str, list[dict]]) -> list[dict]:
    """Merge the per-scheme charge tables into one per-atom table."""
    atoms: dict[int, dict] = {}
    for r in ch.get("mulliken", []):
        a = atoms.setdefault(r["index"], {"index": r["index"], "element": r["element"]})
        a["mulliken"] = r["charge"]
        if "spin" in r:
            a["mulliken_spin"] = r["spin"]
    for r in ch.get("apt", []):
        atoms.setdefault(r["index"], {"index": r["index"], "element": r["element"]})["apt"] = r["charge"]
    for r in ch.get("hirshfeld", []):
        a = atoms.setdefault(r["index"], {"index": r["index"], "element": r["element"]})
        a["hirshfeld"] = r["hirshfeld"]
        if "cm5" in r:
            a["cm5"] = r["cm5"]
    for r in ch.get("npa", []):
        atoms.setdefault(r["index"], {"index": r["index"], "element": r["element"]})["npa"] = r["npa"]
    return [atoms[k] for k in sorted(atoms)]


def _item(key: str, label: str, value: Any, unit: str = "", nd: int = 4, hint: str = "") -> dict:
    if isinstance(value, float):
        value = round(value, nd)
    d = {"key": key, "label": label, "value": value, "unit": unit}
    if hint:
        d["hint"] = hint
    return d


def quantum_descriptors(text: str) -> dict[str, Any]:
    """Parse a Gaussian log and return grouped, UI/export-ready descriptors."""
    raw = parse_gaussian_log(text)
    fmo = frontier(raw["orbitals"])
    cdft = conceptual_dft(fmo.get("homo"), fmo.get("lumo"))
    th = raw["thermo"]
    freqs = raw["frequencies"]
    nimag = sum(1 for f in freqs if f < 0) if freqs else None
    groups: list[dict] = []
    warnings: list[str] = []

    e = raw["scf_energy"]
    groups.append({"id": "calc", "label": "计算信息", "items": [i for i in [
        _item("program", "程序", raw["program"]),
        _item("route", "Route", raw["route"]),
        _item("stoichiometry", "化学式", raw["stoichiometry"]),
        _item("charge", "电荷", raw["charge"]),
        _item("multiplicity", "多重度", raw["multiplicity"]),
        _item("nbasis", "基函数数", raw["nbasis"]),
        _item("n_alpha", "α 电子数", raw["n_alpha"]),
        _item("n_beta", "β 电子数", raw["n_beta"]),
        _item("normal_termination", "正常结束", raw["normal_termination"]),
        _item("elapsed_s", "耗时", raw.get("elapsed_s"), "s", 1),
    ] if i["value"] not in (None, "")]})

    energy_items = [
        _item("scf_method", "SCF 方法", raw["scf_method"]),
        _item("scf_energy", "SCF 电子能量", e, "Hartree", 8),
        _item("scf_energy_ev", "SCF 电子能量", e * HARTREE_TO_EV if e is not None else None, "eV", 4),
        _item("s2", "<S²>", raw.get("s2"), "", 4, "开壳层自旋污染指标,理想值 S(S+1)"),
        _item("excited_total_energy", "激发态总能量", raw["excited_total_energy"], "Hartree", 8),
    ]
    groups.append({"id": "energy", "label": "能量", "items": [i for i in energy_items if i["value"] not in (None, "")]})

    if fmo:
        groups.append({"id": "fmo", "label": "前线轨道 (FMO)", "items": [i for i in [
            _item("homo", "E(HOMO)", fmo.get("homo"), "eV"),
            _item("lumo", "E(LUMO)", fmo.get("lumo"), "eV"),
            _item("gap", "HOMO-LUMO 能隙", fmo.get("gap"), "eV"),
            _item("homo_1", "E(HOMO-1)", fmo.get("homo_1"), "eV"),
            _item("lumo_1", "E(LUMO+1)", fmo.get("lumo_1"), "eV"),
            _item("beta_homo", "β E(HOMO)", fmo.get("beta_homo"), "eV"),
            _item("beta_lumo", "β E(LUMO)", fmo.get("beta_lumo"), "eV"),
        ] if i["value"] is not None]})
    else:
        warnings.append("未找到轨道能级(需 SCF 计算完成且输出含 population 分析)。")

    if cdft:
        groups.append({"id": "cdft", "label": "概念 DFT 反应性指数 (Koopmans 近似)", "items": [i for i in [
            _item("ip", "电离势 I = -E(HOMO)", cdft.get("ip"), "eV"),
            _item("ea", "电子亲和能 A = -E(LUMO)", cdft.get("ea"), "eV"),
            _item("electronegativity", "电负性 χ = (I+A)/2", cdft.get("electronegativity"), "eV"),
            _item("chemical_potential", "化学势 μ = -χ", cdft.get("chemical_potential"), "eV"),
            _item("hardness", "化学硬度 η = (I-A)/2", cdft.get("hardness"), "eV"),
            _item("softness", "化学软度 S = 1/(2η)", cdft.get("softness"), "eV⁻¹"),
            _item("electrophilicity", "亲电指数 ω = μ²/(2η)", cdft.get("electrophilicity"), "eV"),
            _item("electrodonating", "给电子能力 ω⁻", cdft.get("electrodonating"), "eV"),
            _item("electroaccepting", "受电子能力 ω⁺", cdft.get("electroaccepting"), "eV"),
        ] if i["value"] is not None]})

    dip, pol = raw["dipole"], raw["polarizability"]
    elec_items: list[dict] = []
    if dip:
        elec_items += [
            _item("dipole", "偶极矩", dip["total"], "Debye"),
            _item("dipole_x", "μx", dip["x"], "Debye"),
            _item("dipole_y", "μy", dip["y"], "Debye"),
            _item("dipole_z", "μz", dip["z"], "Debye"),
        ]
    if pol:
        elec_items += [
            _item("polarizability_iso", "各向同性极化率 α", pol["iso"], "Bohr³", 3),
            _item("polarizability_iso_ang3", "各向同性极化率 α", pol["iso"] * BOHR3_TO_ANG3, "Å³", 3),
        ]
        if "aniso" in pol:
            elec_items.append(_item("polarizability_aniso", "极化率各向异性 Δα", pol["aniso"], "Bohr³", 3))
    if elec_items:
        groups.append({"id": "electric", "label": "电性质", "items": elec_items})

    if th or freqs:
        th_items = [
            _item("zpe", "零点能校正 ZPE", th.get("zpe"), "Hartree", 6),
            _item("zpe_kcal", "零点能校正 ZPE", th["zpe"] * HARTREE_TO_KCAL if "zpe" in th else None, "kcal/mol", 2),
            _item("corr_enthalpy", "焓校正", th.get("corr_enthalpy"), "Hartree", 6),
            _item("corr_gibbs", "Gibbs 自由能校正", th.get("corr_gibbs"), "Hartree", 6),
            _item("e_zpe", "E + ZPE", th.get("e_zpe"), "Hartree", 6),
            _item("enthalpy", "焓 H", th.get("enthalpy"), "Hartree", 6),
            _item("gibbs", "Gibbs 自由能 G", th.get("gibbs"), "Hartree", 6),
            _item("entropy_term", "熵项 TS = H - G",
                  (th["enthalpy"] - th["gibbs"]) * HARTREE_TO_KCAL
                  if "enthalpy" in th and "gibbs" in th else None, "kcal/mol", 2),
            _item("temperature", "温度", th.get("temperature"), "K", 2),
            _item("pressure", "压力", th.get("pressure"), "atm", 3),
            _item("n_imag", "虚频个数", nimag),
            _item("lowest_freq", "最低频率", min(freqs) if freqs else None, "cm⁻¹", 2),
            _item("n_freq", "振动模式数", len(freqs) if freqs else None),
        ]
        groups.append({"id": "thermo", "label": "热力学 / 振动", "items": [i for i in th_items if i["value"] is not None]})
        if nimag:
            warnings.append(f"存在 {nimag} 个虚频:若为极小点优化,结构未到能量极小;若为过渡态,应恰有 1 个。")

    es = raw["excited_states"]
    if es:
        bright = max(es, key=lambda s: s["f"])
        groups.append({"id": "excited", "label": "激发态 (TD-DFT)", "items": [
            _item("s1_energy", "第一激发态能量 E(S1/T1)", es[0]["energy_ev"], "eV"),
            _item("s1_wavelength", "第一激发态波长", es[0]["wavelength_nm"], "nm", 2),
            _item("s1_f", "第一激发态振子强度 f", es[0]["f"], "", 4),
            _item("max_f_state", "最强吸收态", bright["state"]),
            _item("max_f_wavelength", "最强吸收波长 λmax", bright["wavelength_nm"], "nm", 2),
            _item("max_f", "最大振子强度", bright["f"], "", 4),
        ]})

    if raw["error_termination"] or not raw["normal_termination"]:
        warnings.append("日志未正常结束(Normal termination),数值可能对应中间步骤。")
    if raw.get("s2") is not None and raw["multiplicity"]:
        s = (raw["multiplicity"] - 1) / 2
        ideal = s * (s + 1)
        if raw["multiplicity"] > 1 and raw["s2"] - ideal > 0.1 * max(ideal, 0.75):
            warnings.append(f"<S²>={raw['s2']:.4f} 偏离理想值 {ideal:.4f} 超过 10%,自旋污染明显。")

    atom_charges = _merge_charges(raw["charges"])
    if atom_charges:
        # Pick the most physically reliable scheme present for global min/max stats.
        for scheme in ("npa", "cm5", "hirshfeld", "apt", "mulliken"):
            vals = [a[scheme] for a in atom_charges if scheme in a]
            if vals:
                q_max, q_min = max(vals), min(vals)
                elec_grp = next((g for g in groups if g["id"] == "electric"), None)
                q_items = [
                    _item("q_scheme", "统计电荷方案", scheme.upper()),
                    _item("q_max", "最大原子电荷 q_max", q_max, "e", 4),
                    _item("q_min", "最小原子电荷 q_min", q_min, "e", 4),
                    _item("q_span", "电荷极差 Δq", q_max - q_min, "e", 4),
                ]
                if elec_grp is not None:
                    elec_grp["items"].extend(q_items)
                else:
                    groups.append({"id": "electric", "label": "电性质", "items": q_items})
                break

    groups = [g for g in groups if g["items"]]

    if raw.get("optimization_converged") is False:
        warnings.append("几何优化未收敛(未见 Optimization completed / Stationary point found)。")

    flat: dict[str, Any] = {}
    for g in groups:
        for it in g["items"]:
            flat[it["key"]] = it["value"]

    has_cm5 = any("cm5" in r for r in raw["charges"]["hirshfeld"])
    return {
        "groups": groups,
        "atom_charges": atom_charges,
        "charge_schemes": [k for k, v in raw["charges"].items() if v]
                          + (["cm5"] if has_cm5 else []),
        "excited_states": es[:30],
        "frequencies": freqs[:20],
        "warnings": warnings,
        "flat": flat,
    }


def summarize(text: str) -> dict[str, Any]:
    """Tiny job-ledger summary (stored on the job after completion)."""
    try:
        raw = parse_gaussian_log(text)
    except Exception:
        return {}
    fmo = frontier(raw["orbitals"])
    freqs = raw["frequencies"]
    out = {
        "energy": raw["scf_energy"],
        "homo_ev": _r(fmo.get("homo"), 4),
        "lumo_ev": _r(fmo.get("lumo"), 4),
        "gap_ev": _r(fmo.get("gap"), 4),
        "dipole_debye": _r(raw["dipole"]["total"], 4) if raw["dipole"] else None,
        "gibbs": raw["thermo"].get("gibbs"),
        "n_imag": sum(1 for f in freqs if f < 0) if freqs else None,
    }
    return {k: v for k, v in out.items() if v is not None}
