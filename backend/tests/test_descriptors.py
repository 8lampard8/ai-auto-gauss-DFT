"""Tests for the Gaussian output parser and descriptor extraction.

Run from ``backend/``:  python -m pytest -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.chemistry import gaussian_parser as gp
from app.chemistry.descriptors import rdkit_descriptors
from app.chemistry.importer import from_gjf, from_smiles

DATA = Path(__file__).parent / "data"
WATER = (DATA / "water_optfreq.log").read_text(encoding="utf-8")


def test_termination_multistep():
    assert gp.terminated_normally(WATER)
    # step 2 started but never finished -> not successful
    crashed = WATER.split(" Link1:")[0] + " Link1:  Proceeding to internal job step number  2.\n SCF Done"
    assert not gp.terminated_normally(crashed)
    assert not gp.terminated_normally(WATER + "\n Error termination via Lnk1e in l502.exe")
    assert not gp.terminated_normally("")


def test_parse_core_quantities():
    raw = gp.parse_gaussian_log(WATER)
    assert raw["program"].startswith("Gaussian 16")
    assert raw["route"].startswith("#p opt freq B3LYP/6-31G(d)")
    assert "solvent=water" in raw["route"]
    assert raw["charge"] == 0 and raw["multiplicity"] == 1
    assert raw["nbasis"] == 25
    assert raw["n_alpha"] == 5 and raw["n_beta"] == 5
    assert raw["scf_energy"] == pytest.approx(-76.4089651231)
    assert raw["optimization_converged"] is True
    # last orbital block wins (earlier block contains garbage values)
    assert raw["orbitals"]["alpha_occ"][-1] == pytest.approx(-0.29230)
    assert min(raw["orbitals"]["alpha_virt"]) == pytest.approx(0.06639)
    assert raw["dipole"]["total"] == pytest.approx(2.6187)
    assert raw["polarizability"]["iso"] == pytest.approx((7.005 + 5.300 + 6.200) / 3)
    assert raw["frequencies"] == pytest.approx([1713.0012, 3727.6631, 3849.4567])
    assert raw["thermo"]["gibbs"] == pytest.approx(-76.405592)
    assert raw["thermo"]["temperature"] == pytest.approx(298.15)
    assert raw["elapsed_s"] == pytest.approx(20.5)


def test_charges():
    raw = gp.parse_gaussian_log(WATER)
    ch = raw["charges"]
    assert [r["charge"] for r in ch["mulliken"]] == pytest.approx([-0.794565, 0.397283, 0.397283])
    assert [r["charge"] for r in ch["apt"]] == pytest.approx([-0.6113, 0.30565, 0.30565])
    assert ch["hirshfeld"][0]["cm5"] == pytest.approx(-0.700211)
    assert ch["npa"][0]["npa"] == pytest.approx(-0.97432)
    assert len(ch["npa"]) == 3


def test_quantum_descriptors_grouped():
    q = gp.quantum_descriptors(WATER)
    flat = q["flat"]
    homo = -0.29230 * gp.HARTREE_TO_EV
    lumo = 0.06639 * gp.HARTREE_TO_EV
    assert flat["homo"] == pytest.approx(homo, abs=1e-3)
    assert flat["gap"] == pytest.approx(lumo - homo, abs=1e-3)
    eta = (lumo - homo) / 2
    chi = -(homo + lumo) / 2
    assert flat["hardness"] == pytest.approx(eta, abs=1e-3)
    assert flat["electrophilicity"] == pytest.approx(chi ** 2 / (2 * eta), abs=1e-3)
    assert flat["n_imag"] == 0
    assert {a["index"] for a in q["atom_charges"]} == {1, 2, 3}
    assert {"mulliken", "apt", "hirshfeld", "cm5", "npa"} <= set(q["atom_charges"][0])
    assert not q["warnings"]


OPEN_SHELL_TD = """
 Charge =  0 Multiplicity = 2
 SCF Done:  E(UB3LYP) =  -39.8000000000     A.U. after   12 cycles
 S**2 before annihilation     0.7600,   after     0.7500
 Alpha  occ. eigenvalues --  -10.20000  -0.70000  -0.40000  -0.20000
 Alpha virt. eigenvalues --    0.01000   0.10000
  Beta  occ. eigenvalues --  -10.19000  -0.69000  -0.39000
  Beta virt. eigenvalues --   -0.05000   0.12000
 Mulliken charges and spin densities:
               1          2
     1  C   -0.300000   1.100000
     2  H    0.300000  -0.100000
 Sum of Mulliken charges =   0.00000   1.00000
 Excited State   1:  2.010-A      3.1000 eV  399.95 nm  f=0.0010  <S**2>=0.760
 Excited State   2:  2.020-A      4.5000 eV  275.52 nm  f=0.2500  <S**2>=0.770
 Normal termination of Gaussian 16 at Sat Nov 21 10:00:30 2026.
"""


def test_open_shell_and_excited_states():
    q = gp.quantum_descriptors(OPEN_SHELL_TD)
    f = q["flat"]
    assert f["homo"] == pytest.approx(-0.2 * gp.HARTREE_TO_EV, abs=1e-3)       # alpha SOMO
    assert f["lumo"] == pytest.approx(-0.05 * gp.HARTREE_TO_EV, abs=1e-3)      # beta LUMO
    assert f["s2"] == pytest.approx(0.76)
    assert f["max_f_state"] == 2
    assert f["max_f_wavelength"] == pytest.approx(275.52)
    assert q["atom_charges"][0]["mulliken_spin"] == pytest.approx(1.1)


def test_error_hints():
    assert "SCF 不收敛" in gp.extract_gaussian_error(
        "Convergence failure -- run terminated.\n Error termination via Lnk1e in l502.exe", 1)
    assert "l9999" in gp.extract_gaussian_error(
        "blah\n Error termination via Lnk1e in /opt/g16/l9999.exe at Sat", 1)


def test_summary():
    s = gp.summarize(WATER)
    assert s["n_imag"] == 0 and "gap_ev" in s and s["energy"] < 0


def test_rdkit_descriptors_smiles_and_xyz():
    m = from_smiles("CC(=O)Oc1ccccc1C(=O)O", "aspirin")
    r = rdkit_descriptors(m, full=True)
    f = r["flat"]
    assert r["perception"] == "molblock"
    assert f["formula"] == "C9H8O4"
    assert f["mol_wt"] == pytest.approx(180.159, abs=0.01)
    assert f["hbd"] == 1 and f["hba"] == 3
    assert f["lipinski_violations"] == 0
    assert "radius_of_gyration" in f
    assert len(r["all"]) > 150

    # gjf import has coordinates only -> bonds perceived from geometry
    gjf = "#p sp b3lyp/6-31g*\n\nethanol\n\n0 1\n" + "\n".join(
        f"{a.element} {a.x:.6f} {a.y:.6f} {a.z:.6f}" for a in from_smiles("CCO").atoms) + "\n\n"
    r2 = rdkit_descriptors(from_gjf(gjf))
    assert r2["perception"] == "xyz+bond-orders"
    assert r2["flat"]["canonical_smiles"] == "CCO"
