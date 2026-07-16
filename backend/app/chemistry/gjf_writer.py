"""Gaussian .gjf writer.

Builds a well-formed Gaussian 16 input file from a Molecule (cartesian
geometry) and a MethodSpec.
"""
from __future__ import annotations

from ..schemas import MethodSpec, Molecule
from .basis_sets import normalize_basis


def generate_gjf(molecule: Molecule, spec: MethodSpec) -> str:
    if not molecule.atoms:
        raise ValueError("分子无坐标,无法生成 gjf")

    # Normalise the basis keyword to Gaussian's canonical form (e.g.
    # def2-TZVP -> Def2TZVP) so the route line is valid.
    basis = normalize_basis(spec.basis)

    # --- Link 0 ------------------------------------------------------------
    link0 = [
        "%chk=job.chk",
        f"%mem={spec.memory}",
        f"%nprocshared={spec.nproc}",
    ]

    # --- Route section -----------------------------------------------------
    route_tokens: list[str] = []
    if spec.route:
        route_tokens.append(spec.route)
    route_tokens.append(f"{spec.functional}/{basis}")
    if spec.dispersion:
        route_tokens.append(spec.dispersion)
    if spec.extra:
        route_tokens.append(spec.extra)
    if spec.scrf:
        route_tokens.append(spec.scrf)
    route_line = "# " + " ".join(route_tokens)

    # --- Geometry ----------------------------------------------------------
    atom_lines = "\n".join(
        f"{a.element:<2s} {a.x:>14.6f} {a.y:>14.6f} {a.z:>14.6f}"
        for a in molecule.atoms
    )
    title = spec.title or molecule.name or "title"

    return (
        "\n".join(link0)
        + "\n"
        + route_line
        + "\n\n"
        + title
        + "\n\n"
        + f"{spec.charge} {spec.multiplicity}\n"
        + atom_lines
        + "\n\n"
    )
