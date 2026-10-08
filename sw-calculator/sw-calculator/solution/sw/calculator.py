"""Stillinger-Weber ASE calculator: energy, forces, stress and Hessian.

Neighbours come from ase.neighborlist.primitive_neighbor_list, which returns
every periodic image inside the cutoff (several images of the same atom in
small cells). All terms are evaluated per neighbour vector, so self-images and
repeated images need no special handling: derivatives are taken with respect
to the bond vectors and scattered onto atoms with np.add.at.
"""

import numpy as np
from ase.calculators.calculator import Calculator, PropertyNotImplementedError, all_changes
from ase.neighborlist import primitive_neighbor_list

from .potential import read_sw


class StillingerWeber(Calculator):
    implemented_properties = ["energy", "free_energy", "forces", "stress"]

    def __init__(self, potential, **kwargs):
        super().__init__(**kwargs)
        self.potential = str(potential)
        self.table = read_sw(self.potential)
        self.elements = sorted({k[0] for k in self.table})
        index = {e: n for n, e in enumerate(self.elements)}
        ns = len(self.elements)
        self._index = index
        two = np.zeros((8, ns, ns))
        three = np.zeros((2, ns, ns, ns))
        have2 = np.zeros((ns, ns), bool)
        for (e1, e2, e3), p in self.table.items():
            i, j, k = index[e1], index.get(e2), index.get(e3)
            if j is None or k is None:
                raise ValueError(f"element {e2 if j is None else e3} has no self entry")
            three[:, i, j, k] = (p["lambda"] * p["epsilon"], p["costheta0"])
            if j == k:
                two[:, i, j] = (p["epsilon"], p["sigma"], p["a"], p["A"], p["B"], p["p"], p["q"], p["gamma"])
                have2[i, j] = True
        if not have2.all():
            raise ValueError("missing (i, j, j) entries in potential file")
        self._two = two
        self._three = three
        self._cut = two[2] * two[1]

    # ------------------------------------------------------------------ setup
    def _species(self, atoms):
        try:
            return np.array([self._index[s] for s in atoms.get_chemical_symbols()], int)
        except KeyError as err:
            raise ValueError(f"element {err.args[0]} not in {self.potential}") from None

    def _neighbours(self, atoms):
        spec = self._species(atoms)
        cell = np.asarray(atoms.cell.array, float)
        pbc = np.asarray(atoms.pbc, bool)
        pos = atoms.get_positions()
        i, j, d = primitive_neighbor_list("ijD", pbc, cell, pos, float(self._cut.max()),
                                          self_interaction=False)
        r = np.linalg.norm(d, axis=1)
        keep = r < self._cut[spec[i], spec[j]]
        i, j, d, r = i[keep], j[keep], d[keep], r[keep]
        order = np.argsort(i, kind="stable")
        return spec, i[order], j[order], d[order], r[order]

    @staticmethod
    def _triplets(i):
        """All index pairs (m, n), m < n, of neighbour entries sharing a centre."""
        if len(i) == 0:
            return np.zeros(0, int), np.zeros(0, int)
        starts = np.r_[0, np.flatnonzero(np.diff(i)) + 1]
        ends = np.r_[starts[1:], len(i)]
        group_end = np.repeat(ends, ends - starts)
        later = group_end - np.arange(len(i)) - 1
        first = np.repeat(np.arange(len(i)), later)
        total = int(later.sum())
        if total == 0:
            return first, first
        offs = np.arange(total) - np.repeat(np.cumsum(later) - later, later)
        return first, first + offs + 1

    # ------------------------------------------------------------- core terms
    def _terms(self, atoms, order):
        """Energy plus derivatives with respect to bond vectors up to `order`."""
        spec, i, j, d, r = self._neighbours(atoms)
        si, sj = spec[i], spec[j]
        eps, sig, a, A, B, p, q, gam = (t[si, sj] for t in self._two)
        u = d / r[:, None]

        # two-body, half weight per directed pair
        x = sig / r
        Pv = B * x ** p - x ** q
        dP = (-p * B * x ** p + q * x ** q) / r
        ddP = (p * (p + 1) * B * x ** p - q * (q + 1) * x ** q) / r ** 2
        s = r - a * sig
        Ev = np.exp(sig / s)
        dE = -sig / s ** 2 * Ev
        ddE = Ev * ((sig / s ** 2) ** 2 + 2 * sig / s ** 3)
        pref = 0.5 * A * eps
        phi = pref * Pv * Ev
        dphi = pref * (dP * Ev + Pv * dE)
        energy = phi.sum()
        out = {"i": i, "j": j, "d": d, "energy2": phi, "g2": dphi[:, None] * u}
        if order >= 2:
            ddphi = pref * (ddP * Ev + 2 * dP * dE + Pv * ddE)
            uu = u[:, :, None] * u[:, None, :]
            eye = np.eye(3)[None]
            out["K2"] = ddphi[:, None, None] * uu + (dphi / r)[:, None, None] * (eye - uu)

        # three-body
        t1, t2 = self._triplets(i)
        out["t1"], out["t2"] = t1, t2
        if len(t1):
            le = self._three[0][si[t1], sj[t1], sj[t2]]
            c0 = self._three[1][si[t1], sj[t1], sj[t2]]
            gs = gam * sig
            h = np.exp(gs / s)
            dh = -gs / s ** 2 * h
            ddh = h * ((gs / s ** 2) ** 2 + 2 * gs / s ** 3)
            u1, u2 = u[t1], u[t2]
            r1, r2 = r[t1], r[t2]
            c = np.sum(u1 * u2, axis=1)
            g = (c - c0) ** 2
            dg = 2 * (c - c0)
            h1, h2 = h[t1], h[t2]
            dc1 = (u2 - c[:, None] * u1) / r1[:, None]
            dc2 = (u1 - c[:, None] * u2) / r2[:, None]
            # gradient of f = le * g(c) * h1 * h2 with respect to (D1, D2)
            gc = np.concatenate([dc1, dc2], axis=1)                              # (T, 6)
            gh1 = np.concatenate([dh[t1][:, None] * u1, np.zeros_like(u1)], axis=1)
            gh2 = np.concatenate([np.zeros_like(u2), dh[t2][:, None] * u2], axis=1)
            f = le * g * h1 * h2
            grad = le[:, None] * ((dg * h1 * h2)[:, None] * gc
                                  + (g * h2)[:, None] * gh1 + (g * h1)[:, None] * gh2)
            energy = energy + f.sum()
            out["energy3"] = f
            out["g3"] = grad
            if order >= 2:
                T = len(t1)
                eye = np.eye(3)[None]
                u1u1 = u1[:, :, None] * u1[:, None, :]
                u2u2 = u2[:, :, None] * u2[:, None, :]
                Hc = np.zeros((T, 6, 6))
                Hc[:, :3, :3] = -(u1[:, :, None] * dc1[:, None, :] + dc1[:, :, None] * u1[:, None, :]) / r1[:, None, None] \
                    - c[:, None, None] * (eye - u1u1) / (r1 ** 2)[:, None, None]
                Hc[:, 3:, 3:] = -(u2[:, :, None] * dc2[:, None, :] + dc2[:, :, None] * u2[:, None, :]) / r2[:, None, None] \
                    - c[:, None, None] * (eye - u2u2) / (r2 ** 2)[:, None, None]
                cross = ((eye - u2u2) / r2[:, None, None] - u1[:, :, None] * dc2[:, None, :]) / r1[:, None, None]
                Hc[:, :3, 3:] = cross
                Hc[:, 3:, :3] = np.transpose(cross, (0, 2, 1))
                Hh1 = np.zeros((T, 6, 6))
                Hh1[:, :3, :3] = ddh[t1][:, None, None] * u1u1 + (dh[t1] / r1)[:, None, None] * (eye - u1u1)
                Hh2 = np.zeros((T, 6, 6))
                Hh2[:, 3:, 3:] = ddh[t2][:, None, None] * u2u2 + (dh[t2] / r2)[:, None, None] * (eye - u2u2)
                hsum = h2[:, None] * gh1 + h1[:, None] * gh2
                outer = lambda x, y: x[:, :, None] * y[:, None, :]  # noqa: E731
                M = (2.0 * h1 * h2)[:, None, None] * outer(gc, gc) \
                    + (dg * h1 * h2)[:, None, None] * Hc \
                    + dg[:, None, None] * (outer(gc, hsum) + outer(hsum, gc)) \
                    + g[:, None, None] * (h2[:, None, None] * Hh1 + h1[:, None, None] * Hh2
                                          + outer(gh1, gh2) + outer(gh2, gh1))
                out["M3"] = le[:, None, None] * M
        out["energy"] = float(energy)
        return out

    # --------------------------------------------------------------- outputs
    def calculate(self, atoms=None, properties=("energy",), system_changes=all_changes):
        super().calculate(atoms, properties, system_changes)
        atoms = self.atoms
        n = len(atoms)
        t = self._terms(atoms, 1)
        i, j, d = t["i"], t["j"], t["d"]
        grad = np.zeros((n, 3))
        np.add.at(grad, j, t["g2"])
        np.add.at(grad, i, -t["g2"])
        virial = np.einsum("na,nb->ab", t["g2"], d)
        if len(t["t1"]):
            t1, t2 = t["t1"], t["t2"]
            g1, g2 = t["g3"][:, :3], t["g3"][:, 3:]
            np.add.at(grad, j[t1], g1)
            np.add.at(grad, j[t2], g2)
            np.add.at(grad, i[t1], -(g1 + g2))
            virial += np.einsum("na,nb->ab", g1, d[t1]) + np.einsum("na,nb->ab", g2, d[t2])
        self.results["energy"] = t["energy"]
        self.results["free_energy"] = t["energy"]
        self.results["forces"] = -grad
        if atoms.pbc.all():
            sym = 0.5 * (virial + virial.T) / atoms.get_volume()
            self.results["stress"] = sym[[0, 1, 2, 1, 0, 0], [0, 1, 2, 2, 2, 1]]
        elif "stress" in properties:
            raise PropertyNotImplementedError("stress requires periodic boundaries in all directions")

    def get_hessian(self, atoms=None):
        """Dense (3N, 3N) matrix of second derivatives of the energy, eV/Angstrom^2."""
        atoms = self.atoms if atoms is None else atoms
        n = len(atoms)
        t = self._terms(atoms, 2)
        i, j = t["i"], t["j"]
        H = np.zeros((n, n, 3, 3))
        K = t["K2"]
        np.add.at(H, (j, j), K)
        np.add.at(H, (i, i), K)
        np.add.at(H, (i, j), -K)
        np.add.at(H, (j, i), -K)
        if len(t["t1"]):
            M = t["M3"]
            ci, cj, ck = i[t["t1"]], j[t["t1"]], j[t["t2"]]
            M11, M12, M21, M22 = M[:, :3, :3], M[:, :3, 3:], M[:, 3:, :3], M[:, 3:, 3:]
            np.add.at(H, (cj, cj), M11)
            np.add.at(H, (ck, ck), M22)
            np.add.at(H, (cj, ck), M12)
            np.add.at(H, (ck, cj), M21)
            np.add.at(H, (ci, ci), M11 + M12 + M21 + M22)
            np.add.at(H, (ci, cj), -(M11 + M21))
            np.add.at(H, (cj, ci), -(M11 + M12))
            np.add.at(H, (ci, ck), -(M12 + M22))
            np.add.at(H, (ck, ci), -(M21 + M22))
        return H.transpose(0, 2, 1, 3).reshape(3 * n, 3 * n)
