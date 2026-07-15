"""Molecule import / persistence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..chemistry.importer import import_molecule
from ..chemistry.name_resolver import resolve_smiles
from ..molecules_store import delete as store_delete, list_all, load, save
from ..schemas import ImportByNameRequest, ImportRequest, Molecule, UpdateStructureRequest
from ..settings_store import load as load_settings

router = APIRouter(tags=["molecules"])


@router.post("/molecules/import", response_model=Molecule)
def import_molecule_endpoint(req: ImportRequest) -> Molecule:
    settings = load_settings()
    try:
        mol = import_molecule(
            req.source, req.content, req.filename, req.mime, req.name, settings,
            provider_id=req.provider_id or None,
            model=req.model or None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # pragma: no cover - defensive
        raise HTTPException(500, f"{type(e).__name__}: {e}")
    return save(mol)


@router.post("/molecules/import-by-name", response_model=Molecule)
def import_by_name(req: ImportByNameRequest) -> Molecule:
    """Resolve a molecule name (CN/EN) to SMILES and import it."""
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "名称为空")
    smiles = resolve_smiles(name)
    if not smiles:
        raise HTTPException(404, f"未能解析「{name}」的 SMILES(PubChem/CIR 均无结果)")
    try:
        mol = import_molecule("smiles", smiles, name=name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return save(mol)


@router.get("/molecules")
def list_molecules() -> dict:
    return {"molecules": list_all()}


@router.get("/molecules/{mid}", response_model=Molecule)
def get_molecule(mid: str) -> Molecule:
    try:
        return load(mid)
    except FileNotFoundError:
        raise HTTPException(404, f"molecule {mid} not found")


@router.put("/molecules/{mid}", response_model=Molecule)
def update_molecule_structure(mid: str, req: UpdateStructureRequest) -> Molecule:
    """Re-build a molecule in place from a new SMILES (used by the 2D/3D editor
    so editing doesn't spawn duplicate molecules). Keeps the same id/name."""
    try:
        existing = load(mid)
    except FileNotFoundError:
        raise HTTPException(404, f"molecule {mid} not found")
    try:
        mol = import_molecule("smiles", req.smiles.strip(), name=existing.name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    mol.id = mid
    mol.created_at = existing.created_at
    return save(mol)


@router.delete("/molecules/{mid}")
def delete_molecule(mid: str) -> dict:
    store_delete(mid)
    return {"ok": True}
