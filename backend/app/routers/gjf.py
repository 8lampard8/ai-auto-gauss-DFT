"""gjf generation + method recommendation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..chemistry.basis_sets import COMMON_BASIS_SETS, validate_basis
from ..chemistry.gjf_writer import generate_gjf
from ..chemistry.method_recommender import recommend
from ..molecules_store import load
from ..schemas import GenerateGjfRequest, MethodSpec, RecommendRequest

router = APIRouter(tags=["gjf"])


@router.post("/gjf/recommend", response_model=MethodSpec)
def recommend_method(req: RecommendRequest) -> MethodSpec:
    try:
        mol = load(req.molecule_id)
    except FileNotFoundError:
        raise HTTPException(404, f"molecule {req.molecule_id} not found")
    charge = req.charge if req.charge is not None else mol.charge
    mult = req.multiplicity if req.multiplicity is not None else mol.multiplicity
    return recommend(
        task=req.task,
        solvent=req.solvent,
        accuracy=req.accuracy,
        charge=charge,
        multiplicity=mult,
    )


@router.post("/gjf/generate")
def generate(req: GenerateGjfRequest) -> dict:
    try:
        mol = load(req.molecule_id)
    except FileNotFoundError:
        raise HTTPException(404, f"molecule {req.molecule_id} not found")
    try:
        gjf = generate_gjf(mol, req.spec)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ok, msg = validate_basis(req.spec.basis)
    return {"gjf": gjf, "spec": req.spec, "basis_valid": ok,
            "basis_warning": "" if ok else msg}


@router.get("/gjf/basis-sets")
def list_basis_sets() -> dict:
    """Common valid Gaussian basis sets (reference: gaussian.com/basissets)."""
    return {"basis_sets": COMMON_BASIS_SETS}


@router.get("/gjf/basis-sets/validate")
def validate_basis_endpoint(basis: str) -> dict:
    ok, message = validate_basis(basis)
    return {"valid": ok, "message": message}
