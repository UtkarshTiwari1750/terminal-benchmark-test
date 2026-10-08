"""Reference solver: second-order, well-balanced, positivity-preserving
finite volumes for the 2D shallow-water equations with wetting and drying.

Scheme: MUSCL (minmod) reconstruction of depth, free surface and velocity,
hydrostatic reconstruction at faces, HLL fluxes, unsplit x/y update,
SSP-RK2 (Heun) in time.
"""

import numpy as np

DRY = 1e-10          # depth below which momentum is discarded
DESING = 1e-8        # velocity desingularisation scale
CFL = 0.4
BOUNDARIES = ("wall", "periodic", "open")


def _minmod(a, b):
    return np.where(a * b > 0.0, np.sign(a) * np.minimum(np.abs(a), np.abs(b)), 0.0)


def _velocity(h, q):
    h2 = h * h
    return np.where(h > DRY, 2.0 * h * q / (h2 + np.maximum(h2, DESING * DESING)), 0.0)


def _pad(a, boundary, axis, kind):
    """Two ghost layers along one axis. kind: 'scalar' or 'normal' momentum."""
    if boundary == "periodic":
        mode = "wrap"
    elif boundary == "open":
        mode = "edge"
    else:
        mode = "symmetric"
    width = [(0, 0), (0, 0)]
    width[axis] = (2, 2)
    out = np.pad(a, width, mode=mode)
    if boundary == "wall" and kind == "normal":
        sl = [slice(None), slice(None)]
        sl[axis] = slice(0, 2)
        out[tuple(sl)] *= -1.0
        sl[axis] = slice(-2, None)
        out[tuple(sl)] *= -1.0
    return out


def _faces(a):
    """Minmod-limited left/right face values of padded array along axis -1.

    Returns (minus, plus): value at the right face of cell i (from i) and at
    the left face of cell i (from i), for cells 1..n+2 of the padded array.
    """
    d = np.diff(a, axis=-1)
    s = _minmod(d[..., :-1], d[..., 1:])  # slopes for padded cells 1..n+2
    c = a[..., 1:-1]
    return c + 0.5 * s, c - 0.5 * s


def _hll(hL, uL, vL, hR, uR, vR, g):
    cL = np.sqrt(g * hL)
    cR = np.sqrt(g * hR)
    sL = np.minimum(uL - cL, uR - cR)
    sR = np.maximum(uL + cL, uR + cR)
    qL, qR = hL * uL, hR * uR
    FL = (qL, qL * uL + 0.5 * g * hL * hL, qL * vL)
    FR = (qR, qR * uR + 0.5 * g * hR * hR, qR * vR)
    UL = (hL, qL, hL * vL)
    UR = (hR, qR, hR * vR)
    out = []
    denom = sR - sL
    safe = np.where(denom > 0, denom, 1.0)
    for fl, fr, ul, ur in zip(FL, FR, UL, UR):
        mid = (sR * fl - sL * fr + sL * sR * (ur - ul)) / safe
        f = np.where(sL >= 0, fl, np.where(sR <= 0, fr, mid))
        out.append(np.where(denom > 0, f, 0.0))
    return out


def _residual_axis(h, qn, qt, z, boundary, g):
    """Flux divergence and source along the last axis (cell widths = 1).

    qn: normal momentum, qt: tangential momentum.
    Returns (dh, dqn, dqt) for the interior cells, plus max wave speed.
    """
    hp = _pad(h, boundary, 1, "scalar")
    qnp = _pad(qn, boundary, 1, "normal")
    qtp = _pad(qt, boundary, 1, "scalar")
    zp = _pad(z, boundary, 1, "scalar")
    eta = hp + zp
    up = _velocity(hp, qnp)
    vp = _velocity(hp, qtp)

    hm, hpl = _faces(hp)          # cells 1..n+2
    em, epl = _faces(eta)
    um, upl = _faces(up)
    vm, vpl = _faces(vp)
    hm = np.maximum(hm, 0.0)
    hpl = np.maximum(hpl, 0.0)
    zm, zpl = em - hm, epl - hpl

    # interface k between padded cells k+1 and k+2 (k = 0..n)
    hL, zL, uL, vL = hm[..., :-1], zm[..., :-1], um[..., :-1], vm[..., :-1]
    hR, zR, uR, vR = hpl[..., 1:], zpl[..., 1:], upl[..., 1:], vpl[..., 1:]
    zs = np.maximum(zL, zR)
    hLs = np.maximum(0.0, hL + zL - zs)
    hRs = np.maximum(0.0, hR + zR - zs)
    F = _hll(hLs, uL, vL, hRs, uR, vR, g)

    # hydrostatic corrections (cell on left gets +, on right gets -)
    corrL = 0.5 * g * (hL * hL - hLs * hLs)
    corrR = 0.5 * g * (hR * hR - hRs * hRs)

    # interior cells are padded cells 2..n+1 -> face index i-1 (left), i (right)
    Fh_r, Fh_l = F[0][..., 1:], F[0][..., :-1]
    Fn_r = F[1][..., 1:] + corrL[..., 1:]
    Fn_l = F[1][..., :-1] + corrR[..., :-1]
    Ft_r, Ft_l = F[2][..., 1:], F[2][..., :-1]

    hci_m, hci_p = hm[..., 1:-1], hpl[..., 1:-1]   # interior right/left face depths
    zci_m, zci_p = zm[..., 1:-1], zpl[..., 1:-1]
    src = -0.5 * g * (hci_m + hci_p) * (zci_m - zci_p)

    dh = -(Fh_r - Fh_l)
    dqn = -(Fn_r - Fn_l) + src
    dqt = -(Ft_r - Ft_l)

    hi = hp[..., 2:-2]
    speed = np.abs(up[..., 2:-2]) + np.sqrt(g * hi)
    return dh, dqn, dqt, speed


def _rhs(h, hu, hv, z, dx, dy, boundary, g):
    dhx, dqx, dtx, ax = _residual_axis(h, hu, hv, z, boundary, g)
    if h.shape[0] > 1:
        dhy, dqy, dty, ay = (a.T for a in _residual_axis(h.T, hv.T, hu.T, z.T, boundary, g))
    else:
        dhy = dqy = dty = 0.0
        ay = np.zeros_like(h)
    rate = ax / dx + (ay / dy if h.shape[0] > 1 else 0.0)
    return (dhx / dx + dhy / dy, dqx / dx + dty / dy, dtx / dx + dqy / dy), rate


def _clean(h, hu, hv):
    h = np.maximum(h, 0.0)
    dry = h <= DRY
    return h, np.where(dry, 0.0, hu), np.where(dry, 0.0, hv)


def simulate(h, hu, hv, z, dx, dy, times, g=9.81, boundary="wall"):
    if boundary not in BOUNDARIES:
        raise ValueError(f"boundary must be one of {BOUNDARIES}")
    h, hu, hv, z = (np.array(a, dtype=float) for a in (h, hu, hv, z))
    if h.ndim != 2 or not (h.shape == hu.shape == hv.shape == z.shape):
        raise ValueError("h, hu, hv, z must be equal-shape 2D arrays (ny, nx)")
    times = [float(t) for t in times]
    if any(b < a for a, b in zip(times, times[1:])) or (times and times[0] < 0):
        raise ValueError("times must be non-negative and non-decreasing")
    h, hu, hv = _clean(h, hu, hv)
    t = 0.0
    out = []
    for target in times:
        while t < target:
            k1, rate = _rhs(h, hu, hv, z, dx, dy, boundary, g)
            rmax = float(np.max(rate)) if rate.size else 0.0
            dt = CFL / rmax if rmax > 0 else target - t
            if t + dt >= target or target - (t + dt) < 1e-12 * max(1.0, target):
                dt = target - t
            h1, hu1, hv1 = _clean(h + dt * k1[0], hu + dt * k1[1], hv + dt * k1[2])
            k2, _ = _rhs(h1, hu1, hv1, z, dx, dy, boundary, g)
            h = 0.5 * (h + h1 + dt * k2[0])
            hu = 0.5 * (hu + hu1 + dt * k2[1])
            hv = 0.5 * (hv + hv1 + dt * k2[2])
            h, hu, hv = _clean(h, hu, hv)
            t = target if dt == target - t else t + dt
        out.append((h.copy(), hu.copy(), hv.copy()))
    return out
