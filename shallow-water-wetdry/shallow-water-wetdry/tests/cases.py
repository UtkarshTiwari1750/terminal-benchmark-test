"""Test problems with independent references (analytic or invariant-based).

Each case builds initial data, calls the submitted ``simulate`` and returns a
dict of scalar metrics. Thresholds live in grade.py. Nothing here depends on
the reference solver.
"""

import math
import time

import numpy as np

G = 9.81


# ---------------------------------------------------------------- analytic refs

def stoker(x, t, hl, hr, x0=0.5, g=G):
    """Exact wet dam break (left rarefaction, right shock), zero initial velocity."""
    cl = math.sqrt(g * hl)

    def f(hm):
        return 2 * (cl - math.sqrt(g * hm)) - (hm - hr) * math.sqrt(0.5 * g * (1 / hm + 1 / hr))

    lo, hi = hr, hl
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    hm = 0.5 * (lo + hi)
    um = 2 * (cl - math.sqrt(g * hm))
    cm = math.sqrt(g * hm)
    s = hm * um / (hm - hr)
    xi = (x - x0) / t
    h = np.where(xi <= -cl, hl,
        np.where(xi <= um - cm, ((2 * cl - xi) / 3) ** 2 / g,
        np.where(xi <= s, hm, hr)))
    u = np.where(xi <= -cl, 0.0,
        np.where(xi <= um - cm, 2 * (cl + xi) / 3,
        np.where(xi <= s, um, 0.0)))
    return h, h * u


def ritter(x, t, hl, x0=0.5, g=G):
    """Exact dam break onto a dry flat bed."""
    cl = math.sqrt(g * hl)
    xi = (x - x0) / t
    h = np.where(xi <= -cl, hl, np.where(xi <= 2 * cl, ((2 * cl - xi) / 3) ** 2 / g, 0.0))
    u = np.where((xi > -cl) & (xi <= 2 * cl), 2 * (cl + xi) / 3, 0.0)
    return h, h * u


def thacker(x, y, t, a=1.0, h0=0.5, B=0.5, g=G):
    """Planar oscillating surface in a paraboloid / parabola (Thacker 1981).

    Bed z = h0 (r^2/a^2 - 1); velocity is uniform in the wet region.
    Valid in 1D (y = 0) and 2D.
    """
    w = math.sqrt(2 * g * h0) / a
    s = -B * w * math.cos(w * t) / g
    c = B * B * math.sin(w * t) ** 2 / (2 * g)
    r2 = x * x + y * y
    h = np.maximum(0.0, h0 * (1 - r2 / a ** 2) + s * x + c)
    u = B * math.sin(w * t)
    return h, h * u, np.zeros_like(h), w


def thacker_bed(x, y, a=1.0, h0=0.5):
    return h0 * ((x * x + y * y) / a ** 2 - 1)


# ---------------------------------------------------------------- helpers

def _row(a):
    return np.asarray(a, dtype=float)[None, :]


def _run(simulate, h, hu, hv, z, dx, dy, times, boundary):
    start = time.perf_counter()
    out = simulate(h.copy(), hu.copy(), hv.copy(), z.copy(), dx, dy, list(times), g=G, boundary=boundary)
    elapsed = time.perf_counter() - start
    out = list(out)
    if len(out) != len(times):
        raise ValueError("simulate returned wrong number of snapshots")
    clean = []
    for snap in out:
        if len(snap) != 3:
            raise ValueError("each snapshot must be (h, hu, hv)")
        arrs = tuple(np.asarray(a, dtype=float) for a in snap)
        if any(a.shape != h.shape for a in arrs):
            raise ValueError("snapshot shape mismatch")
        clean.append(arrs)
    return clean, elapsed


def _finite(snaps):
    return all(np.all(np.isfinite(a)) for s in snaps for a in s)


def _min_depth(snaps):
    return float(min(np.min(s[0]) for s in snaps))


# ---------------------------------------------------------------- cases

def lake_1d(simulate):
    """Still lake over a bed with an emerged bump and partially wet cells."""
    nx = 200
    dx = 1.0 / nx
    x = (np.arange(nx) + 0.5) * dx
    z = 0.8 * np.exp(-((x - 0.5) / 0.08) ** 2) + 0.3 * np.exp(-((x - 0.15) / 0.05) ** 2) \
        + 0.15 * np.sin(13 * x) ** 2
    eta = 0.6
    h = np.maximum(0.0, eta - z)
    snaps, el = _run(simulate, _row(h), _row(0 * h), _row(0 * h), _row(z), dx, 1.0, [0.5, 2.0], "wall")
    return {
        "finite": _finite(snaps),
        "min_depth": _min_depth(snaps),
        "max_momentum": float(max(np.max(np.abs(s[1])) + np.max(np.abs(s[2])) for s in snaps)),
        "max_depth_change": float(max(np.max(np.abs(s[0][0] - h)) for s in snaps)),
        "dry_cells": int(np.sum(h == 0)),
        "seconds": el,
    }


def lake_2d(simulate):
    """Still lake with an island, a submerged ridge and a dry shore in 2D."""
    n = 80
    dx = dy = 1.0 / n
    c = (np.arange(n) + 0.5) * dx
    X, Y = np.meshgrid(c, c)
    z = 0.9 * np.exp(-((X - 0.4) ** 2 + (Y - 0.55) ** 2) / 0.01) \
        + 0.4 * np.exp(-((X - 0.75) ** 2) / 0.003) * (0.5 + Y) + 0.7 * np.maximum(0, X + Y - 1.6) * 3
    eta = 0.5
    h = np.maximum(0.0, eta - z)
    zero = np.zeros_like(h)
    snaps, el = _run(simulate, h, zero, zero, z, dx, dy, [0.3, 1.0], "wall")
    return {
        "finite": _finite(snaps),
        "min_depth": _min_depth(snaps),
        "max_momentum": float(max(np.max(np.abs(s[1])) + np.max(np.abs(s[2])) for s in snaps)),
        "max_depth_change": float(max(np.max(np.abs(s[0] - h)) for s in snaps)),
        "dry_cells": int(np.sum(h == 0)),
        "seconds": el,
    }


def dam_break(simulate, kind, axis="x"):
    """Stoker (wet) or Ritter (dry) dam break; axis='y' runs it along the columns."""
    n = 400
    dx = 1.0 / n
    x = (np.arange(n) + 0.5) * dx
    hl, hr = 1.0, (0.1 if kind == "wet" else 0.0)
    h = np.where(x < 0.5, hl, hr)
    t = 0.1
    if axis == "x":
        H, Z = _row(h), _row(0 * h)
        snaps, el = _run(simulate, H, 0 * H, 0 * H, Z, dx, 1.0, [t], "open")
        hn, qn, qt = snaps[0][0][0], snaps[0][1][0], snaps[0][2][0]
    else:
        H = np.repeat(h[:, None], 3, axis=1)
        snaps, el = _run(simulate, H, 0 * H, 0 * H, 0 * H, 1.0 / 3, dx, [t], "open")
        hn, qn, qt = snaps[0][0][:, 1], snaps[0][2][:, 1], snaps[0][1][:, 1]
    he, qe = stoker(x, t, hl, hr) if kind == "wet" else ritter(x, t, hl)
    return {
        "finite": _finite(snaps),
        "min_depth": _min_depth(snaps),
        "l1_depth": float(np.sum(np.abs(hn - he)) * dx),
        "l1_discharge": float(np.sum(np.abs(qn - qe)) * dx),
        "max_tangential": float(np.max(np.abs(qt))),
        "seconds": el,
    }


def convergence(simulate):
    """Self-convergence on a smooth periodic flow over a smooth bed."""
    def run(n):
        dx = 1.0 / n
        x = (np.arange(n) + 0.5) * dx
        # cell averages of smooth data (5-point Gauss per cell)
        gp, gw = np.polynomial.legendre.leggauss(5)
        pts = x[:, None] + 0.5 * dx * gp[None, :]
        avg = lambda f: (f(pts) * gw).sum(axis=1) / 2.0
        z = avg(lambda s: 0.1 * np.sin(2 * np.pi * s) ** 2)
        eta = avg(lambda s: 1.0 + 0.04 * np.sin(2 * np.pi * s + 0.4))
        hu = avg(lambda s: 0.25 + 0.05 * np.cos(2 * np.pi * s))
        h = eta - z
        snaps, el = _run(simulate, _row(h), _row(hu), _row(0 * h), _row(z), dx, 1.0, [0.06], "periodic")
        return snaps[0], el

    sols = {}
    total = 0.0
    finite = True
    for n in (100, 200, 400, 800, 1600):
        s, el = run(n)
        sols[n] = s
        total += el
        finite = finite and _finite([s])

    def coarsen(a, k):
        return a.reshape(a.shape[0], -1, k).mean(axis=2)

    diffs = []
    for n in (100, 200, 400, 800):
        d = 0.0
        for comp in (0, 1):
            fine = coarsen(sols[2 * n][comp], 2)
            d += float(np.sum(np.abs(fine - sols[n][comp])) / n)
        diffs.append(d)
    orders = [math.log2(diffs[i] / diffs[i + 1]) if diffs[i + 1] > 0 else 0.0 for i in range(3)]
    mass = [float(np.sum(sols[n][0])) / n for n in sols]
    return {"finite": finite, "orders": orders, "differences": diffs,
            "mass_spread": float(max(mass) - min(mass)), "seconds": total}


def thacker_1d(simulate):
    """Moving shoreline in a parabola; one full period with wall boundaries."""
    n = 400
    L = 4.0
    dx = L / n
    x = -L / 2 + (np.arange(n) + 0.5) * dx
    z = thacker_bed(x, 0 * x)
    h0, q0, _, w = thacker(x, 0 * x, 0.0)
    period = 2 * math.pi / w
    times = [period / 4, period / 2, period]
    snaps, el = _run(simulate, _row(h0), _row(q0), _row(0 * h0), _row(z), dx, 1.0, times, "wall")
    errs, qerrs = [], []
    for t, s in zip(times, snaps):
        he, qe, _, _ = thacker(x, 0 * x, t)
        errs.append(float(np.sum(np.abs(s[0][0] - he)) * dx))
        qerrs.append(float(np.sum(np.abs(s[1][0] - qe)) * dx))
    m0 = float(np.sum(h0) * dx)
    mass = max(abs(float(np.sum(s[0]) * dx) - m0) / m0 for s in snaps)
    return {"finite": _finite(snaps), "min_depth": _min_depth(snaps),
            "l1_depth": max(errs), "l1_discharge": max(qerrs),
            "relative_mass_error": mass, "seconds": el}


def thacker_2d(simulate):
    """Planar oscillation in a paraboloid on a 2D grid, half a period."""
    n = 100
    L = 4.0
    dx = dy = L / n
    c = -L / 2 + (np.arange(n) + 0.5) * dx
    X, Y = np.meshgrid(c, c)
    z = thacker_bed(X, Y)
    h0, q0, p0, w = thacker(X, Y, 0.0)
    period = 2 * math.pi / w
    times = [period / 4, period / 2]
    snaps, el = _run(simulate, h0, q0, p0, z, dx, dy, times, "wall")
    errs, qerrs, sym = [], [], []
    for t, s in zip(times, snaps):
        he, qe, _, _ = thacker(X, Y, t)
        errs.append(float(np.sum(np.abs(s[0] - he)) * dx * dy))
        qerrs.append(float(np.sum(np.abs(s[1] - qe)) * dx * dy + np.sum(np.abs(s[2])) * dx * dy))
        sym.append(float(np.max(np.abs(s[0] - s[0][::-1, :]))))
    m0 = float(np.sum(h0))
    mass = max(abs(float(np.sum(s[0])) - m0) / m0 for s in snaps)
    return {"finite": _finite(snaps), "min_depth": _min_depth(snaps),
            "l1_depth": max(errs), "l1_discharge": max(qerrs),
            "mirror_asymmetry": max(sym), "relative_mass_error": mass, "seconds": el}


def performance(simulate):
    """Fine-grid 2D moving shoreline: must be both accurate and fast."""
    n = 256
    L = 4.0
    dx = dy = L / n
    c = -L / 2 + (np.arange(n) + 0.5) * dx
    X, Y = np.meshgrid(c, c)
    z = thacker_bed(X, Y)
    h0, q0, p0, w = thacker(X, Y, 0.0)
    t = 0.5 * math.pi / w
    snaps, el = _run(simulate, h0, q0, p0, z, dx, dy, [t], "wall")
    he, _, _, _ = thacker(X, Y, t)
    m0 = float(np.sum(h0))
    return {"finite": _finite(snaps), "min_depth": _min_depth(snaps),
            "l1_depth": float(np.sum(np.abs(snaps[0][0] - he)) * dx * dy),
            "relative_mass_error": abs(float(np.sum(snaps[0][0])) - m0) / m0, "seconds": el}


CASES = {
    "lake_1d": lake_1d,
    "lake_2d": lake_2d,
    "stoker_x": lambda s: dam_break(s, "wet", "x"),
    "ritter_x": lambda s: dam_break(s, "dry", "x"),
    "ritter_y": lambda s: dam_break(s, "dry", "y"),
    "convergence": convergence,
    "thacker_1d": thacker_1d,
    "thacker_2d": thacker_2d,
    "performance": performance,
}
