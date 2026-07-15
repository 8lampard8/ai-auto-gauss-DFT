"""Molecule persistence helpers (JSON files under data/uploads/)."""
from __future__ import annotations

import datetime
from collections import Counter
from pathlib import Path

from .config import UPLOADS_DIR
from .schemas import Molecule, MoleculeSummary


def path(mid: str) -> Path:
    return UPLOADS_DIR / f"{mid}.json"


def save(mol: Molecule) -> Molecule:
    if not mol.created_at:
        mol.created_at = datetime.datetime.now().isoformat(timespec="seconds")
    path(mol.id).write_text(mol.model_dump_json(indent=2), encoding="utf-8")
    return mol


def load(mid: str) -> Molecule:
    p = path(mid)
    if not p.exists():
        raise FileNotFoundError(mid)
    return Molecule.model_validate_json(p.read_text(encoding="utf-8"))


def delete(mid: str) -> bool:
    p = path(mid)
    if p.exists():
        p.unlink()
        return True
    return False


def formula(atoms) -> str:
    c = Counter(a.element for a in atoms)
    parts: list[tuple[str, int]] = []
    if c.get("C"):
        parts.append(("C", c["C"]))
    if c.get("H"):
        parts.append(("H", c["H"]))
    for el in sorted(k for k in c if k not in ("C", "H")):
        parts.append((el, c[el]))
    return "".join(f"{el}{n if n > 1 else ''}" for el, n in parts)


def list_all() -> list[MoleculeSummary]:
    items: list[MoleculeSummary] = []
    for p in sorted(UPLOADS_DIR.glob("mol-*.json"),
                    key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            mol = Molecule.model_validate_json(p.read_text(encoding="utf-8"))
            items.append(MoleculeSummary(
                id=mol.id, name=mol.name, source=mol.source,
                formula=formula(mol.atoms), natoms=len(mol.atoms),
                charge=mol.charge, multiplicity=mol.multiplicity,
            ))
        except Exception:
            continue
    return items
