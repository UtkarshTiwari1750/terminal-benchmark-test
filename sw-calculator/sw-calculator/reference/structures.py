"""Deterministic fixture structures (author tooling)."""

import numpy as np
from ase import Atoms
from ase.build import bulk, make_supercell

A_SI = 5.431


def _rattle(atoms, amp, seed):
    rng = np.random.default_rng(seed)
    atoms.positions += rng.uniform(-amp, amp, atoms.positions.shape)
    return atoms


def _strain(atoms, eps):
    deform = np.eye(3) + np.asarray(eps)
    atoms.set_cell(atoms.cell.array @ deform, scale_atoms=True)
    return atoms


def _random_cell(symbols, cell, rmin, seed, max_tries=200000):
    rng = np.random.default_rng(seed)
    cell = np.asarray(cell, float)
    frac = []
    for _ in range(max_tries):
        f = rng.random(3)
        ok = True
        for g in frac:
            d = f - g
            d -= np.round(d)
            for img in np.array(np.meshgrid([-1, 0, 1], [-1, 0, 1], [-1, 0, 1])).T.reshape(-1, 3):
                if np.linalg.norm((d + img) @ cell) < rmin:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            frac.append(f)
            if len(frac) == len(symbols):
                break
    if len(frac) < len(symbols):
        raise RuntimeError("could not place atoms")
    return Atoms(symbols, scaled_positions=np.array(frac), cell=cell, pbc=True)


def structures():
    """Return [(name, atoms, potential_file, want_hessian)]."""
    out = []

    a = _rattle(bulk("Si", "diamond", a=A_SI, cubic=True), 0.06, 1)
    out.append(("si_diamond", a, "Si.sw", True))

    a = bulk("Si", "diamond", a=A_SI)
    a = _strain(a, [[0.02, 0.03, 0.0], [0.0, -0.01, 0.04], [0.01, 0.0, 0.015]])
    out.append(("si_primitive_triclinic", _rattle(a, 0.08, 2), "Si.sw", True))

    a = Atoms("Si", positions=[[0.3, -0.2, 0.1]],
              cell=[[2.55, 0.0, 0.0], [0.62, 2.48, 0.0], [-0.35, 0.41, 2.60]], pbc=True)
    out.append(("si_one_atom_cell", a, "Si.sw", True))

    cell = np.array([[7.1, 0.0, 0.0], [1.9, 6.6, 0.0], [-1.3, 1.1, 6.9]])
    a = _random_cell(["Si"] * 16, cell, 2.15, 3)
    rng = np.random.default_rng(4)
    a.positions += rng.integers(-2, 3, (16, 3)) @ cell   # unwrapped positions
    out.append(("si_random_triclinic", a, "Si.sw", True))

    a = bulk("Si", "diamond", a=A_SI, cubic=True).repeat((1, 1, 2))
    a = _rattle(a, 0.05, 5)
    a.cell[2] = [0.0, 0.0, 30.0]
    a.pbc = [True, True, False]
    out.append(("si_slab", a, "Si.sw", True))

    big = bulk("Si", "diamond", a=A_SI, cubic=True).repeat(2)
    centre = np.array([A_SI * 0.6, A_SI * 0.55, A_SI * 0.62])
    near = np.argsort(np.linalg.norm(big.positions - centre, axis=1))[:10]
    cl = _rattle(Atoms("Si10", positions=big.positions[near], pbc=False), 0.08, 6)
    out.append(("si_cluster", cl, "Si.sw", True))

    a = _strain(bulk("Si", "diamond", a=A_SI, cubic=True), [[0.01, 0.02, 0.0], [0.0, 0.0, 0.0], [0.0, 0.01, -0.02]])
    out.append(("si_mod_diamond", _rattle(a, 0.07, 7), "Si_mod.sw", True))

    a = bulk("SiGe", "zincblende", a=5.53)
    a = _strain(a, [[0.0, 0.02, 0.01], [0.0, 0.015, 0.0], [0.03, 0.0, -0.01]])
    out.append(("sige_primitive", _rattle(a, 0.07, 8), "SiGe.sw", True))

    cell = np.array([[7.3, 0.0, 0.0], [-1.2, 7.0, 0.0], [0.9, -1.5, 7.2]])
    a = _random_cell(["Si", "Ge"] * 8, cell, 2.2, 9)
    out.append(("sige_random_triclinic", a, "SiGe.sw", True))

    a = bulk("Si", "diamond", a=A_SI, cubic=True).repeat(2)
    sym = np.array(a.get_chemical_symbols())
    sym[np.random.default_rng(10).permutation(64)[:24]] = "Ge"
    a.set_chemical_symbols(sym)
    a = _strain(a, [[0.01, 0.005, 0.0], [0.0, -0.005, 0.01], [0.0, 0.0, 0.0]])
    out.append(("sige_64", _rattle(a, 0.1, 11), "SiGe.sw", False))
    return out
