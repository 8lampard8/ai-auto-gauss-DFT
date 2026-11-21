"""Integration tests for descriptor endpoints and core bug fixes.

Run from ``backend/``:  python -m pytest -q
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.chemistry.importer import from_gaussian_log, from_smiles
from app.exec.local_runner import _cap_gjf_text, _cap_mem, _mem_to_mb
from app.jobs_store import create as create_job, delete as delete_job, get as get_job, update as update_job
from app.main import app
from app.molecules_store import delete as delete_molecule, load as load_molecule, save as save_molecule

DATA = Path(__file__).parent / "data"
WATER_LOG = (DATA / "water_optfreq.log").read_text(encoding="utf-8")

WATER_LOG_WITH_ORIENT = (
    WATER_LOG.split(" SCF Done:")[0]
    + """
                         Standard orientation:
 ---------------------------------------------------------------------
 Center     Atomic      Atomic             Coordinates (Angstroms)
 Number     Number       Type             X           Y           Z
 ---------------------------------------------------------------------
      1          8           0        0.000000    0.000000    0.117300
      2          1           0        0.000000    0.757200   -0.469200
      3          1           0        0.000000   -0.757200   -0.469200
 ---------------------------------------------------------------------
 SCF Done:"""
    + WATER_LOG.split(" SCF Done:", 1)[1]
)


def test_from_gaussian_log_standard_and_input_orientation():
    m = from_gaussian_log(WATER_LOG_WITH_ORIENT, "water_std")
    assert len(m.atoms) == 3
    assert [a.element for a in m.atoms] == ["O", "H", "H"]
    assert m.charge == 0 and m.multiplicity == 1
    assert "B3LYP/6-31G(d)" in m.route

    nosymm_log = WATER_LOG_WITH_ORIENT.replace("Standard orientation:", "Input orientation:")
    m2 = from_gaussian_log(nosymm_log, "water_nosymm")
    assert [a.element for a in m2.atoms] == ["O", "H", "H"]


def test_mem_capping_units():
    assert _mem_to_mb("8GB") == 8192
    assert _mem_to_mb("1500MB") == 1500
    assert _mem_to_mb("200MW") == 1600
    assert _cap_mem("8GB", 1500) == "1500MB"
    assert _cap_mem("1000MB", 1500) == "1000MB"

    patched = _cap_gjf_text("%mem=8GB\n%nprocshared=16\n# opt b3lyp/6-31g*\n")
    assert "%mem=1500MB" in patched
    assert "%nprocshared=4" in patched


def test_molecule_path_traversal_blocked():
    with pytest.raises(FileNotFoundError):
        load_molecule("../../etc/passwd")
    with pytest.raises(FileNotFoundError):
        load_molecule("..\\settings")


def test_job_cancel_skip_race():
    jid = "job-test-race01"
    delete_job(jid)
    try:
        create_job(jid, status="running", kind="local")
        update_job(jid, status="cancelled")
        # Watcher thread tries to overwrite with failed -> skipped!
        res = update_job(jid, _skip_if_status=("cancelled",), status="failed", error="killed")
        assert res is not None and res["status"] == "cancelled"
        assert get_job(jid)["status"] == "cancelled"
    finally:
        delete_job(jid)


def test_descriptor_endpoints_end_to_end(tmp_path: Path):
    client = TestClient(app)

    # 1. Molecule descriptors
    mol = save_molecule(from_smiles("CCO", "test_ethanol"))
    jid = "job-test-desc01"
    log_file = tmp_path / "water.log"
    log_file.write_text(WATER_LOG_WITH_ORIENT, encoding="utf-8")
    delete_job(jid)
    create_job(jid, status="succeeded", kind="local",
               molecule_id=mol.id, molecule_name="water",
               spec_label="B3LYP/6-31G(d)", log_path=str(log_file))

    try:
        r = client.get(f"/api/descriptors/molecule/{mol.id}?full=true")
        assert r.status_code == 200
        data = r.json()
        assert data["kind"] == "molecule"
        assert data["flat"]["formula"] == "C2H6O"
        assert "all" in data["structure"] and len(data["structure"]["all"]) > 150

        # 2. Direct log parse (both quantum + RDKit from Standard orientation!)
        r2 = client.post("/api/descriptors/parse-log", json={
            "content": WATER_LOG_WITH_ORIENT,
            "filename": "water_optfreq.log",
            "full": False,
            "include_rdkit": True,
        })
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["quantum"]["flat"]["n_imag"] == 0
        assert d2["quantum"]["flat"]["q_scheme"] == "NPA"
        assert d2["structure"] is not None
        assert d2["structure"]["flat"]["formula"] == "H2O"

        # 3. Job descriptors + summary backfill
        r3 = client.get(f"/api/descriptors/job/{jid}")
        assert r3.status_code == 200
        d3 = r3.json()
        assert d3["quantum"]["flat"]["dipole"] == pytest.approx(2.6187, abs=1e-3)
        assert d3["structure"] is not None
        assert get_job(jid).get("summary", {}).get("n_imag") == 0

        # 4. Batch extraction (molecule + job + SMILES + bad SMILES)
        r4 = client.post("/api/descriptors/batch", json={
            "molecule_ids": [mol.id],
            "job_ids": [jid],
            "smiles_list": [
                "c1ccccc1,benzene",
                "acetone CC(=O)C",
                "INVALID((SMILES",
            ],
            "include_all_rdkit": False,
        })
        assert r4.status_code == 200
        d4 = r4.json()
        assert d4["count"] == 4
        assert len(d4["errors"]) == 1
        names = [row["name"] for row in d4["rows"]]
        assert "test_ethanol" in names and "benzene" in names and "acetone" in names

        # 5. CSV export (UTF-8 BOM)
        r5 = client.post("/api/descriptors/export", json={
            "molecule_ids": [mol.id],
            "job_ids": [jid],
            "smiles_list": ["c1ccccc1,benzene"],
            "format": "csv",
        })
        assert r5.status_code == 200
        assert r5.content.startswith(b"\xef\xbb\xbf")
        rows = list(csv.DictReader(io.StringIO(r5.content.decode("utf-8-sig"))))
        assert len(rows) == 3
        assert "mol_wt" in rows[0] and "homo" in rows[0]

        # 6. JSON export
        r6 = client.post("/api/descriptors/export", json={
            "smiles_list": ["CCO,ethanol"],
            "format": "json",
        })
        assert r6.status_code == 200
        parsed = json.loads(r6.content.decode("utf-8"))
        assert parsed["count"] == 1

        # 7. Chat with molecule context + descriptor keyword (Mock provider)
        r7 = client.post("/api/chat", json={
            "messages": [{"role": "user", "content": "怎么提取分子描述符?"}],
            "provider_id": "mock",
            "context": {"molecule_id": mol.id},
        })
        assert r7.status_code == 200
        assert "RDKit" in r7.text and "done" in r7.text
    finally:
        delete_molecule(mol.id)
        delete_job(jid)
