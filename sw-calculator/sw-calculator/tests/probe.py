"""Isolated runner for the submitted calculator.

Usage: probe.py MODE INPUT.npz OUTPUT.npz
Only arrays and strings cross the process boundary; references never enter this process.
"""
import sys
import time
import traceback

sys.path.insert(0, "/app")

import numpy as np  # noqa: E402
from ase import Atoms  # noqa: E402
from ase.build import bulk  # noqa: E402

mode, source, target = sys.argv[1], sys.argv[2], sys.argv[3]
with np.load(source, allow_pickle=False) as data:
    inp = {k: data[k] for k in data.files}

from sw import StillingerWeber  # noqa: E402

out = {}


def record(key, func):
    try:
        out[key] = np.asarray(func(), dtype=float)
    except Exception:  # noqa: BLE001 - report every failure to the grader
        out[key + "_error"] = np.array(traceback.format_exc()[-2000:])


def structure():
    return Atoms(numbers=inp["numbers"], positions=inp["positions"], cell=inp["cell"], pbc=inp["pbc"])


potential = "/app/potentials/" + str(inp.get("potential", "Si.sw"))

if mode == "efs":
    calc = StillingerWeber(potential)
    # reuse: the same instance first evaluates an unrelated structure
    warm = bulk("Si", "diamond", a=5.5, cubic=True)
    warm.calc = calc
    warm.get_forces()
    atoms = structure()
    atoms.calc = calc
    record("energy", atoms.get_potential_energy)
    record("forces", atoms.get_forces)
    if atoms.pbc.all():
        record("stress", atoms.get_stress)

elif mode == "hessian":
    calc = StillingerWeber(potential)
    atoms = structure()
    atoms.calc = calc
    record("hessian", lambda: calc.get_hessian(atoms))

elif mode == "scale":
    atoms = structure().repeat(tuple(int(k) for k in inp["repeat"]))
    atoms.calc = StillingerWeber(potential)

    def run():
        start = time.perf_counter()
        e = atoms.get_potential_energy()
        f = atoms.get_forces()
        s = atoms.get_stress()
        out["forces"] = np.asarray(f, float)
        out["stress"] = np.asarray(s, float)
        out["seconds"] = np.array(time.perf_counter() - start)
        return e
    record("energy", run)

elif mode == "md":
    def run():
        rng = np.random.default_rng(int(inp["seed"]))
        atoms = bulk("Si", "diamond", a=5.431, cubic=True).repeat(2)
        atoms.positions += rng.normal(0.0, 0.05, atoms.positions.shape)
        atoms.calc = StillingerWeber(potential)
        masses = atoms.get_masses()[:, None]                 # amu
        conv = 1.0 / 103.642697   # 1 amu*(A/fs)^2 = 103.642697 eV; v in A/fs, m in amu
        kT = float(inp["temperature"]) * 8.617333262e-5
        v = rng.normal(size=atoms.positions.shape) * np.sqrt(kT * conv / masses)
        v -= (masses * v).sum(axis=0) / masses.sum()
        dt = float(inp["dt"])
        f = atoms.get_forces()
        totals, momenta = [], []
        for step in range(int(inp["steps"]) + 1):
            ke = 0.5 * float(np.sum(masses * v * v)) / conv
            totals.append(atoms.get_potential_energy() + ke)
            momenta.append(np.abs((masses * v).sum(axis=0)).max())
            if step == int(inp["steps"]):
                break
            v += 0.5 * dt * f / masses * conv
            atoms.positions = atoms.positions + dt * v
            atoms.wrap()
            f = atoms.get_forces()
            v += 0.5 * dt * f / masses * conv
        out["momentum"] = np.array(momenta)
        out["natoms"] = np.array(len(atoms))
        return np.array(totals)
    record("total_energy", run)

np.savez(target, **out)
