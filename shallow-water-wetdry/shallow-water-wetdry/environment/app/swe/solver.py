"""Legacy 2D shallow-water solver used by the flood-screening scripts.

First-order Rusanov finite volumes with a cell-centred bed-slope source.
Known field complaints: still reservoirs develop currents over rough beds,
runs crash or go negative where the shoreline moves, and results are only
first-order accurate.
"""

import numpy as np

BOUNDARIES = ("wall", "periodic", "open")


def _pad(a, boundary, axis, normal=False):
    width = [(0, 0), (0, 0)]
    width[axis] = (1, 1)
    mode = {"periodic": "wrap", "open": "edge", "wall": "symmetric"}[boundary]
    out = np.pad(a, width, mode=mode)
    if boundary == "wall" and normal:
        idx = [slice(None), slice(None)]
        for s in (0, -1):
            idx[axis] = s
            out[tuple(idx)] *= -1.0
    return out


def _sweep(h, qn, qt, z, boundary, g):
    hp = _pad(h, boundary, 1)
    qp = _pad(qn, boundary, 1, normal=True)
    tp = _pad(qt, boundary, 1)
    zp = _pad(z, boundary, 1)
    u = qp / np.maximum(hp, 1e-12)
    v = tp / np.maximum(hp, 1e-12)
    a = np.abs(u) + np.sqrt(g * np.abs(hp))
    U = (hp, qp, tp)
    F = (qp, qp * u + 0.5 * g * hp * hp, qp * v)
    amax = np.maximum(a[:, :-1], a[:, 1:])
    flux = [0.5 * (f[:, :-1] + f[:, 1:]) - 0.5 * amax * (w[:, 1:] - w[:, :-1]) for f, w in zip(F, U)]
    d = [-(f[:, 1:] - f[:, :-1]) for f in flux]
    d[1] = d[1] - g * h * 0.5 * (zp[:, 2:] - zp[:, :-2])
    return d, a[:, 1:-1]


def simulate(h, hu, hv, z, dx, dy, times, g=9.81, boundary="wall"):
    """Advance cell averages and return [(h, hu, hv), ...] at each requested time."""
    if boundary not in BOUNDARIES:
        raise ValueError(f"boundary must be one of {BOUNDARIES}")
    h, hu, hv, z = (np.array(a, dtype=float) for a in (h, hu, hv, z))
    t = 0.0
    out = []
    for target in times:
        while t < target:
            (dhx, dqx, dtx), ax = _sweep(h, hu, hv, z, boundary, g)
            if h.shape[0] > 1:
                dy_terms, ay = _sweep(h.T, hv.T, hu.T, z.T, boundary, g)
                dhy, dqy, dty = (a.T for a in dy_terms)
                ay = ay.T
                rate = ax / dx + ay / dy
            else:
                dhy = dqy = dty = 0.0
                rate = ax / dx
            dt = min(0.4 / float(np.max(rate)), target - t)
            h = h + dt * (dhx / dx + dhy / dy)
            hu = hu + dt * (dqx / dx + dty / dy)
            hv = hv + dt * (dtx / dx + dqy / dy)
            t += dt
        out.append((h.copy(), hu.copy(), hv.copy()))
    return out
