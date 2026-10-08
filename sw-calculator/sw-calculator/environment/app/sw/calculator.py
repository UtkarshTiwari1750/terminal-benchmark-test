"""Stillinger-Weber calculator for ASE (legacy implementation).

Energy uses the minimum-image convention; forces are central finite
differences of the energy. Stress and Hessian are not implemented.
"""

import itertools

import numpy as np
from ase.calculators.calculator import Calculator, PropertyNotImplementedError, all_changes

from .potential import read_sw


class StillingerWeber(Calculator):
    implemented_properties = ["energy", "free_energy", "forces"]

    def __init__(self, potential, **kwargs):
        super().__init__(**kwargs)
        self.potential = str(potential)
        self.p = read_sw(self.potential)

    def _energy(self, positions, cell, pbc):
        p = self.p
        eps, sig, a = p["epsilon"], p["sigma"], p["a"]
        cut = a * sig
        n = len(positions)
        inv = np.linalg.pinv(cell) if pbc.any() else None

        def vec(i, j):
            d = positions[j] - positions[i]
            if inv is not None:
                f = d @ inv
                f -= np.where(pbc, np.round(f), 0.0)
                d = f @ cell
            return d

        neigh = {i: [] for i in range(n)}
        energy = 0.0
        for i, j in itertools.combinations(range(n), 2):
            d = vec(i, j)
            r = np.linalg.norm(d)
            if r < cut:
                x = sig / r
                energy += p["A"] * eps * (p["B"] * x ** p["p"] - x ** p["q"]) * np.exp(sig / (r - cut))
                neigh[i].append(d)
                neigh[j].append(-d)
        for i in range(n):
            for d1, d2 in itertools.combinations(neigh[i], 2):
                r1, r2 = np.linalg.norm(d1), np.linalg.norm(d2)
                c = d1 @ d2 / (r1 * r2)
                energy += p["lambda"] * eps * (c - p["costheta0"]) ** 2 \
                    * np.exp(p["gamma"] * sig / (r1 - cut)) * np.exp(p["gamma"] * sig / (r2 - cut))
        return energy

    def calculate(self, atoms=None, properties=("energy",), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        if "stress" in properties:
            raise PropertyNotImplementedError("stress is not implemented")
        pos = self.atoms.get_positions()
        cell = self.atoms.cell.array
        pbc = np.asarray(self.atoms.pbc, bool)
        energy = self._energy(pos, cell, pbc)
        self.results["energy"] = energy
        self.results["free_energy"] = energy
        if "forces" in properties:
            h = 1e-5
            forces = np.zeros_like(pos)
            for k in range(len(pos)):
                for ax in range(3):
                    plus, minus = pos.copy(), pos.copy()
                    plus[k, ax] += h
                    minus[k, ax] -= h
                    forces[k, ax] = -(self._energy(plus, cell, pbc) - self._energy(minus, cell, pbc)) / (2 * h)
            self.results["forces"] = forces

    def get_hessian(self, atoms=None):
        raise NotImplementedError("Hessian is not implemented")
