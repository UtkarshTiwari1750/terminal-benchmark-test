"""Independent reference for the Stillinger-Weber task (author tooling, not shipped to the agent).

Energy is a brute-force sum over explicitly enumerated periodic images. It is
written so that positions and cell may be complex: derivatives are then taken
by complex-step differentiation, which is exact to round-off for first
derivatives. No analytic derivative of the potential appears anywhere here.

Neighbour topology is fixed from the real geometry; evaluations then reuse it.
Perturbations used below are <= 2e-3 Angstrom, far smaller than the distance
from any fixture pair to its cutoff where the potential is not already zero.
"""

import itertools
import math

import numpy as np

MARGIN = 0.05   # pairs this close beyond the cutoff stay in the topology; masked at evaluation


def read_sw(path):
    tokens = []
    with open(path) as handle:
        for line in handle:
            tokens.extend(line.split("#", 1)[0].split())
    if len(tokens) % 14:
        raise ValueError("sw file must contain 14 fields per entry")
    table = {}
    for k in range(0, len(tokens), 14):
        e1, e2, e3 = tokens[k:k + 3]
        vals = [float(v) for v in tokens[k + 3:k + 14]]
        table[(e1, e2, e3)] = dict(zip(
            ["epsilon", "sigma", "a", "lambda", "gamma", "costheta0", "A", "B", "p", "q", "tol"], vals))
    return table


class Topology:
    """Brute-force enumeration of neighbour images and triplets."""

    def __init__(self, symbols, positions, cell, pbc, table):
        self.symbols = list(symbols)
        self.table = table
        pos = np.asarray(positions, float)
        cell = np.asarray(cell, float)
        pbc = np.asarray(pbc, bool)
        n = len(pos)
        self.n = n
        self.pbc = pbc

        # wrap periodic directions (energy is invariant); remember the integer shift
        if pbc.any():
            frac = np.linalg.solve(cell.T, pos.T).T
            shift = np.where(pbc, np.floor(frac), 0.0)
        else:
            shift = np.zeros_like(pos)
        self.wrap_shift = shift
        wpos = pos - shift @ cell

        cut = {}
        for (e1, e2, e3), p in table.items():
            if e2 == e3:
                cut[(e1, e2)] = p["a"] * p["sigma"]
        rmax = max(cut.values())

        ranges = []
        for ax in range(3):
            if pbc[ax]:
                other = [cell[(ax + 1) % 3], cell[(ax + 2) % 3]]
                height = abs(np.linalg.det(cell)) / np.linalg.norm(np.cross(*other))
                m = int(math.ceil(rmax / height)) + 1
                ranges.append(range(-m, m + 1))
            else:
                ranges.append(range(0, 1))
        images = np.array(list(itertools.product(*ranges)), float)

        pairs = []      # (i, j, image vector)
        for i in range(n):
            for j in range(n):
                d = wpos[j] + images @ cell - wpos[i]
                r = np.linalg.norm(d, axis=1)
                ok = r < cut[(self.symbols[i], self.symbols[j])] + MARGIN
                if i == j:
                    ok &= np.any(images != 0, axis=1)
                for img in images[ok]:
                    pairs.append((i, j, img))
        self.pi = np.array([p[0] for p in pairs], int)
        self.pj = np.array([p[1] for p in pairs], int)
        self.pimg = np.array([p[2] for p in pairs], float).reshape(-1, 3)

        trip = []
        for i in range(n):
            idx = np.nonzero(self.pi == i)[0]
            trip.extend(itertools.combinations(idx, 2))
        trip = np.array(trip, int).reshape(-1, 2)
        self.t1, self.t2 = trip[:, 0], trip[:, 1]

        # per-pair and per-triplet parameter arrays
        def p2(i, j, key):
            return self.table[(self.symbols[i], self.symbols[j], self.symbols[j])][key]
        keys2 = ["epsilon", "sigma", "a", "A", "B", "p", "q", "gamma"]
        self.P = {k: np.array([p2(i, j, k) for i, j in zip(self.pi, self.pj)], float) for k in keys2}
        ci = self.pi[self.t1]
        cj = self.pj[self.t1]
        ck = self.pj[self.t2]
        ent = [self.table[(self.symbols[a], self.symbols[b], self.symbols[c])] for a, b, c in zip(ci, cj, ck)]
        self.lam_eps = np.array([e["lambda"] * e["epsilon"] for e in ent], float)
        self.cos0 = np.array([e["costheta0"] for e in ent], float)

    def energy(self, positions, cell):
        """Energy for (possibly complex) positions and cell with this topology."""
        positions = np.asarray(positions)
        cell = np.asarray(cell)
        wpos = positions - self.wrap_shift @ cell
        d = wpos[self.pj] + self.pimg @ cell - wpos[self.pi]
        r = np.sqrt(np.sum(d * d, axis=1))
        P = self.P
        cut = P["a"] * P["sigma"]
        inside = np.real(r) < cut
        s = np.where(inside, r - cut, -1.0)
        x = P["sigma"] / r
        e2 = np.where(inside, P["A"] * P["epsilon"] * (P["B"] * x ** P["p"] - x ** P["q"])
                      * np.exp(P["sigma"] / s), 0.0)
        energy = 0.5 * np.sum(e2)
        if len(self.t1):
            d1, d2 = d[self.t1], d[self.t2]
            r1, r2 = r[self.t1], r[self.t2]
            cos = np.sum(d1 * d2, axis=1) / (r1 * r2)
            gs = P["gamma"] * P["sigma"]
            h = np.where(inside, np.exp(gs / s), 0.0)
            energy = energy + np.sum(self.lam_eps * (cos - self.cos0) ** 2 * h[self.t1] * h[self.t2])
        return energy


H_CS = 1e-30


def reference(symbols, positions, cell, pbc, table, hessian=False, delta=1e-3):
    pos = np.asarray(positions, float)
    cell = np.asarray(cell, float)
    top = Topology(symbols, pos, cell, pbc, table)
    n = len(pos)
    out = {"energy": float(np.real(top.energy(pos, cell)))}

    def gradient(p):
        g = np.zeros(3 * n)
        for a in range(3 * n):
            q = p.astype(complex)
            q.reshape(-1)[a] += 1j * H_CS
            g[a] = np.imag(top.energy(q, cell)) / H_CS
        return g

    out["forces"] = -gradient(pos).reshape(n, 3)

    if np.all(pbc):
        vol = abs(np.linalg.det(cell))
        stress = np.zeros(6)
        voigt = [(0, 0), (1, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
        for v, (a, b) in enumerate(voigt):
            eps = np.zeros((3, 3), complex)
            eps[a, b] += 1j * H_CS
            if a != b:
                eps[b, a] += 1j * H_CS
            deform = np.eye(3) + eps
            dE = np.imag(top.energy(pos @ deform, cell @ deform)) / H_CS
            stress[v] = dE / vol / (1 if a == b else 2)
        out["stress"] = stress

    if hessian:
        H = np.zeros((3 * n, 3 * n))
        flat = pos.reshape(-1)
        for b in range(3 * n):
            grads = []
            for s in (-2, -1, 1, 2):
                p = flat.copy()
                p[b] += s * delta
                grads.append(gradient(p.reshape(n, 3)))
            H[:, b] = (grads[0] - 8 * grads[1] + 8 * grads[2] - grads[3]) / (12 * delta)
        out["hessian"] = 0.5 * (H + H.T)
        out["hessian_asymmetry"] = float(np.max(np.abs(H - H.T)))
    return out
