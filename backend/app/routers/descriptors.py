"""Molecular descriptor extraction endpoints (RDKit 2D/3D + Gaussian DFT).

Supports:
- Single saved molecule (RDKit basic / drug-likeness / topology / 3D shape / full 2D)
- Completed Gaussian job (DFT quantum descriptors + structure descriptors)
- Direct Gaussian .log/.out upload (parse quantum + geometry descriptors on the fly)
- Batch extraction across molecules, jobs and raw SMILES lists, with CSV / JSON export
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..chemistry.descriptors import rdkit_descriptors
from ..chemistry.gaussian_parser import quantum_descriptors, summarize
from ..chemistry.importer import from_gaussian_log, from_smiles
from ..jobs_store import get as get_job, update as update_job
from ..molecules_store import load as load_molecule

router = APIRouter(tags=["descriptors"])


class ParseLogRequest(BaseModel):
    content: str
    filename: str = ""
    full: bool = False
    include_rdkit: bool = True


class BatchDescriptorsRequest(BaseModel):
    molecule_ids: list[str] = Field(default_factory=list)
    job_ids: list[str] = Field(default_factory=list)
    smiles_list: list[str] = Field(default_factory=list)
    include_all_rdkit: bool = False


class ExportDescriptorsRequest(BatchDescriptorsRequest):
    format: Literal["csv", "json"] = "csv"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _structure_from_log_or_mol(log_text: str, molecule_id: str, name: str,
                               full: bool) -> tuple[dict[str, Any] | None, list[str]]:
    """Prefer DFT-optimized geometry from the log if bond orders perceive cleanly;
    fall back to the saved molecule (which carries an explicit molblock)."""
    notes: list[str] = []
    log_struct: dict[str, Any] | None = None
    if log_text:
        try:
            log_mol = from_gaussian_log(log_text, name=name)
            log_struct = rdkit_descriptors(log_mol, full=full)
            if log_struct.get("perception") == "xyz+bond-orders":
                return log_struct, notes
        except Exception:
            log_struct = None

    if molecule_id:
        try:
            saved = load_molecule(molecule_id)
            return rdkit_descriptors(saved, full=full), notes
        except Exception:
            pass

    if log_struct is not None:
        return log_struct, notes
    notes.append("未能从任务关联分子或日志坐标构建 RDKit 结构描述符。")
    return None, notes


def _merge_flat(structure: dict | None, quantum: dict | None,
                include_all_rdkit: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if structure:
        out.update(structure.get("flat") or {})
    if quantum:
        # Prefix colliding keys (e.g. route) with qm_ if already present,
        # otherwise keep clean short names for QSAR/ML tables.
        for k, v in (quantum.get("flat") or {}).items():
            key = f"qm_{k}" if k in out else k
            out[key] = v
    if include_all_rdkit and structure and structure.get("all"):
        for k, v in structure["all"].items():
            out[f"rdkit_{k}"] = v
    return out


def _parse_smiles_line(line: str, idx: int) -> tuple[str, str]:
    """Parse a batch SMILES line supporting ``SMILES``, ``SMILES,name``,
    ``SMILES\\tname`` or ``name SMILES``."""
    s = line.strip()
    if "," in s:
        a, b = [x.strip() for x in s.split(",", 1)]
        return (a, b or f"smiles_{idx}")
    parts = s.split()
    if len(parts) == 1:
        return parts[0], f"smiles_{idx}"
    # Decide which token is the SMILES (test with RDKit)
    from rdkit import Chem

    if Chem.MolFromSmiles(parts[0]) is not None:
        return parts[0], " ".join(parts[1:])
    if Chem.MolFromSmiles(parts[-1]) is not None:
        return parts[-1], " ".join(parts[:-1])
    return parts[0], " ".join(parts[1:])


def _run_batch(req: BatchDescriptorsRequest) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    col_order: list[str] = ["source_type", "id", "name"]
    col_seen = set(col_order)

    def _add_row(row: dict[str, Any]) -> None:
        for k in row:
            if k not in col_seen:
                col_seen.add(k)
                col_order.append(k)
        rows.append(row)

    for mid in req.molecule_ids:
        try:
            mol = load_molecule(mid)
            st = rdkit_descriptors(mol, full=req.include_all_rdkit)
            row = {"source_type": "molecule", "id": mol.id, "name": mol.name}
            row.update(_merge_flat(st, None, req.include_all_rdkit))
            _add_row(row)
        except Exception as e:
            errors.append({"source": f"molecule:{mid}", "error": str(e)})

    for jid in req.job_ids:
        try:
            job = get_job(jid)
            if job is None:
                raise FileNotFoundError(f"job {jid} not found")
            log_path = job.get("log_path") or ""
            text = ""
            if log_path and Path(log_path).exists():
                text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
            if not text:
                raise ValueError("任务尚无日志文件")
            qm = quantum_descriptors(text)
            st, _ = _structure_from_log_or_mol(
                text, job.get("molecule_id", ""), job.get("molecule_name", jid),
                full=req.include_all_rdkit,
            )
            row = {
                "source_type": "job",
                "id": jid,
                "name": job.get("molecule_name") or jid,
                "spec": job.get("spec_label") or "",
            }
            row.update(_merge_flat(st, qm, req.include_all_rdkit))
            _add_row(row)
        except Exception as e:
            errors.append({"source": f"job:{jid}", "error": str(e)})

    for idx, raw_line in enumerate(req.smiles_list, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        smi, nm = _parse_smiles_line(line, idx)
        try:
            mol = from_smiles(smi, name=nm)
            st = rdkit_descriptors(mol, full=req.include_all_rdkit)
            row = {"source_type": "smiles", "id": f"smi-{idx}", "name": nm}
            row.update(_merge_flat(st, None, req.include_all_rdkit))
            _add_row(row)
        except Exception as e:
            errors.append({"source": f"smiles:{smi[:40]}", "error": str(e)})

    return {"columns": col_order, "rows": rows, "count": len(rows), "errors": errors}


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@router.get("/descriptors/molecule/{mid}")
def get_molecule_descriptors(mid: str, full: bool = False) -> dict:
    try:
        mol = load_molecule(mid)
    except FileNotFoundError:
        raise HTTPException(404, f"molecule {mid} not found")
    try:
        st = rdkit_descriptors(mol, full=full)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "kind": "molecule",
        "id": mol.id,
        "name": mol.name,
        "structure": st,
        "quantum": None,
        "warnings": list(st.get("warnings") or []),
        "flat": _merge_flat(st, None, full),
    }


@router.get("/descriptors/job/{job_id}")
def get_job_descriptors(job_id: str, full: bool = False) -> dict:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, f"job {job_id} not found")
    log_path = job.get("log_path") or ""
    if not log_path or not Path(log_path).exists():
        raise HTTPException(400, "该任务尚无 Gaussian 日志(.log),无法提取量化描述符")
    text = Path(log_path).read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        raise HTTPException(400, "Gaussian 日志为空")

    qm = quantum_descriptors(text)
    st, notes = _structure_from_log_or_mol(
        text, job.get("molecule_id", ""), job.get("molecule_name", job_id), full=full
    )
    # Backfill summary on older jobs transparently.
    if not job.get("summary") and qm["flat"].get("normal_termination"):
        s = summarize(text)
        if s:
            update_job(job_id, summary=s)

    warnings = list(qm.get("warnings") or [])
    if st:
        warnings.extend(st.get("warnings") or [])
    warnings.extend(notes)

    return {
        "kind": "job",
        "id": job_id,
        "name": job.get("molecule_name") or job_id,
        "spec_label": job.get("spec_label") or "",
        "structure": st,
        "quantum": qm,
        "warnings": warnings,
        "flat": _merge_flat(st, qm, full),
    }


@router.post("/descriptors/parse-log")
def parse_log_descriptors(req: ParseLogRequest) -> dict:
    if not (req.content or "").strip():
        raise HTTPException(400, "日志内容为空")
    name = (req.filename.rsplit(".", 1)[0] if req.filename else "") or "gaussian_log"
    qm = quantum_descriptors(req.content)
    st: dict[str, Any] | None = None
    notes: list[str] = []
    if req.include_rdkit:
        st, notes = _structure_from_log_or_mol(req.content, "", name, full=req.full)

    warnings = list(qm.get("warnings") or [])
    if st:
        warnings.extend(st.get("warnings") or [])
    warnings.extend(notes)

    return {
        "kind": "log",
        "id": name,
        "name": name,
        "structure": st,
        "quantum": qm,
        "warnings": warnings,
        "flat": _merge_flat(st, qm, req.full),
    }


@router.post("/descriptors/batch")
def batch_descriptors(req: BatchDescriptorsRequest) -> dict:
    if not (req.molecule_ids or req.job_ids or req.smiles_list):
        raise HTTPException(400, "请至少选择一个分子、任务或输入至少一条 SMILES")
    return _run_batch(req)


@router.post("/descriptors/export")
def export_descriptors(req: ExportDescriptorsRequest) -> Response:
    if not (req.molecule_ids or req.job_ids or req.smiles_list):
        raise HTTPException(400, "请至少选择一个分子、任务或输入至少一条 SMILES")
    data = _run_batch(req)

    if req.format == "json":
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        return Response(
            content=payload.encode("utf-8"),
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="descriptors.json"'},
        )

    buf = io.StringIO()
    cols = data["columns"]
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for r in data["rows"]:
        writer.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})
    # UTF-8 with BOM so Excel opens Chinese headers/names cleanly.
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="descriptors.csv"'},
    )
