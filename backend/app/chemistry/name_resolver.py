"""Resolve a molecule name (Chinese or English) to a SMILES string.

Primary source: PubChem PUG-REST. Fallback: NCI Chemical Identifier Resolver
(CIR). Also provides a lightweight heuristic extractor that scans free text
for a molecule mention — used by the Mock chat path and as a hint for the
LLM extraction prompt.
"""
from __future__ import annotations

import json
import re
from typing import Any

# C60 (buckminsterfullerene) canonical SMILES - used for all fullerene variants.
_C60_SMILES = (
    "c12c3c4c5c1c6c7c8c2c9c%10c3c%11c%12c4c%13c%14c5c%15c6c%16c7c%17c%18c8"
    "c9c%19c%20c%10c%11c%21c%22c%12c%13c%23c%24c%14c%15c%25c%16c%26c%17c%27"
    "c%18c%19c%28c%20c%21c%29c%22c%23c%30c%24c%25c%26c%31c%27c%28c%29c%30%31"
)

# Common names → SMILES, bilingual. Checked first so the demo works offline
# (no PubChem round-trip) for popular molecules.
COMMON_NAMES: dict[str, str] = {
    "ethanol": "CCO", "乙醇": "CCO",
    "methanol": "CO", "甲醇": "CO",
    "water": "O", "水": "O",
    "methane": "C", "甲烷": "C",
    "ethene": "C=C", "ethylene": "C=C", "乙烯": "C=C",
    "benzene": "c1ccccc1", "苯": "c1ccccc1",
    "toluene": "Cc1ccccc1", "甲苯": "Cc1ccccc1",
    "phenol": "Oc1ccccc1", "苯酚": "Oc1ccccc1",
    "aniline": "Nc1ccccc1", "苯胺": "Nc1ccccc1",
    "acetone": "CC(=O)C", "丙酮": "CC(=O)C",
    "aceticacid": "CC(=O)O", "acetic acid": "CC(=O)O", "乙酸": "CC(=O)O", "醋酸": "CC(=O)O",
    "aspirin": "CC(=O)OC1=CC=CC=C1C(=O)O", "阿司匹林": "CC(=O)OC1=CC=CC=C1C(=O)O",
    "caffeine": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "咖啡因": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "urea": "NC(N)=O", "尿素": "NC(N)=O",
    "glucose": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O", "葡萄糖": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
    "pyridine": "c1ccncc1", "吡啶": "c1ccncc1",
    "naphthalene": "c1ccc2ccccc2c1", "萘": "c1ccc2ccccc2c1",
    # Fullerene is a class; default to C60 (buckminsterfullerene). PubChem
    # doesn't recognise the Chinese name "富勒烯" or the class name "fullerene",
    # so map all common variants directly to the C60 SMILES.
    "fullerene": _C60_SMILES, "富勒烯": _C60_SMILES,
    "buckminsterfullerene": _C60_SMILES, "buckyball": _C60_SMILES,
    "c60": _C60_SMILES, "碳60": _C60_SMILES, "[60]fullerene": _C60_SMILES,
}

# A loose SMILES detector (good enough to short-circuit name resolution).
_SMILES_RE = re.compile(r"^(\s*)([A-Za-z0-9@\[\]()+=#$\-\\\/.]{4,})\s*$")


def _normalize(text: str) -> str:
    return text.strip().lower().replace(" ", "")


def resolve_smiles(name: str) -> str:
    """Resolve a molecule name to a canonical SMILES via PubChem then CIR."""
    name = name.strip()
    if not name:
        return ""
    # 1) common-name dictionary (offline, instant)
    smi = COMMON_NAMES.get(_normalize(name))
    if smi:
        return smi
    # 2) PubChem PUG-REST
    smi = _resolve_pubchem(name)
    if smi:
        return smi
    # 3) NCI CIR fallback
    smi = _resolve_cir(name)
    return smi or ""


def _resolve_pubchem(name: str) -> str:
    import httpx
    from urllib.parse import quote

    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
        f"{quote(name)}/property/CanonicalSMILES/JSON"
    )
    try:
        r = httpx.get(url, timeout=12.0)
        if r.status_code != 200:
            return ""
        data = r.json()
        props = data.get("PropertyTable", {}).get("Properties", [])
        if props:
            return props[0].get("CanonicalSMILES", "")
    except Exception:
        return ""
    return ""


def _resolve_cir(name: str) -> str:
    import httpx
    from urllib.parse import quote

    url = f"https://cactus.nci.nih.gov/chemical/structure/{quote(name)}/smiles"
    try:
        r = httpx.get(url, timeout=12.0)
        if r.status_code != 200:
            return ""
        out = r.text.strip()
        if not out or out.lower().startswith("not found") or "<html" in out.lower():
            return ""
        return out.split()[0]
    except Exception:
        return ""


def heuristic_extract(text: str) -> dict[str, Any]:
    """Scan free text for a molecule mention.

    Returns ``{"name": ..., "smiles": ...|None}`` or ``{}`` if nothing found.
    ``smiles`` is filled from the common-name dict when available; otherwise
    the caller resolves the name via :func:`resolve_smiles`.
    """
    if not text:
        return {}
    low = _normalize(text)

    # 1) explicit SMILES token on its own line / quoted
    for token in re.findall(r"[A-Za-z0-9@\[\]()+=#$\-\\\/.]{6,}", text):
        if _looks_like_smiles(token):
            return {"name": "smiles_input", "smiles": token}

    # 2) common-name dictionary (longest key first for specificity)
    for key in sorted(COMMON_NAMES, key=len, reverse=True):
        k = _normalize(key)
        if k and k in low:
            return {"name": key, "smiles": COMMON_NAMES[key]}

    # 3) regex: a noun phrase after action verbs (计算/算/优化/分析 ...)
    m = re.search(
        r"(?:计算|算|优化|分析|研究|模拟|算一下|计算一下)\s*(?:一下|下)?\s*"
        r"([一-龥A-Za-z0-9]{2,20}?)\s*(?:的|优化|频率|结构|性质|能量|光谱|激发态|$)",
        text,
    )
    if m:
        cand = m.group(1).strip()
        if cand and cand not in ("一下", "一个", "分子"):
            return {"name": cand, "smiles": None}
    return {}


def _looks_like_smiles(token: str) -> bool:
    if not token:
        return False
    # must contain a bond/branch/ring digit typical of SMILES, not be a plain word
    if not re.search(r"[=#\$\-]|[\[\]()]", token):
        return False
    return bool(re.match(r"^[A-Za-z0-9@\[\]()+=#\$\-\\\/.]+$", token))
