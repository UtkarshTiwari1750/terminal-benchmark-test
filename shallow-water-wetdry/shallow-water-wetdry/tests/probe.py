"""Isolated runner: load one simulate() call from .npz, run the submission, save .npz.

Only raw arrays cross the process boundary, so the submission never shares an
interpreter with the reference solutions or the grading logic.
"""
import sys
import time

sys.path.insert(0, "/app")

import numpy as np  # noqa: E402

source, target = sys.argv[1], sys.argv[2]
with np.load(source, allow_pickle=False) as data:
    args = {k: data[k] for k in data.files}

import swe  # noqa: E402

start = time.perf_counter()
snapshots = swe.simulate(args["h"], args["hu"], args["hv"], args["z"],
                         float(args["dx"]), float(args["dy"]),
                         [float(t) for t in args["times"]],
                         g=float(args["g"]), boundary=str(args["boundary"]))
elapsed = time.perf_counter() - start

snapshots = list(snapshots)
arrays = {"count": np.array(len(snapshots)), "seconds": np.array(elapsed)}
for i, snap in enumerate(snapshots):
    snap = tuple(snap)
    if len(snap) != 3:
        raise SystemExit("each snapshot must be a 3-tuple (h, hu, hv)")
    for name, value in zip(("h", "hu", "hv"), snap):
        arrays[f"{name}{i}"] = np.asarray(value, dtype=np.float64)
np.savez(target, **arrays)
