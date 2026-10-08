"""Regenerate tests/fixtures/*.npz from the independent reference.

Usage (from the task root):  python reference/build_fixtures.py
Needs numpy and ase only; does not import the oracle.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from structures import structures  # noqa: E402
from sw_reference import read_sw, reference  # noqa: E402

out_dir = ROOT / "tests" / "fixtures"
out_dir.mkdir(parents=True, exist_ok=True)
for name, atoms, pot, want_h in structures():
    table = read_sw(ROOT / "environment" / "app" / "potentials" / pot)
    ref = reference(atoms.get_chemical_symbols(), atoms.positions, atoms.cell.array, atoms.pbc,
                    table, hessian=want_h)
    data = {
        "numbers": atoms.numbers, "positions": atoms.positions, "cell": atoms.cell.array,
        "pbc": atoms.pbc, "potential": np.array(pot), "energy": np.array(ref["energy"]),
        "forces": ref["forces"],
    }
    if "stress" in ref:
        data["stress"] = ref["stress"]
    if "hessian" in ref:
        data["hessian"] = ref["hessian"]
    np.savez(out_dir / f"{name}.npz", **data)
    print(f"{name:24s} N={len(atoms):3d} keys={sorted(k for k in data if k in ('stress', 'hessian'))}")
