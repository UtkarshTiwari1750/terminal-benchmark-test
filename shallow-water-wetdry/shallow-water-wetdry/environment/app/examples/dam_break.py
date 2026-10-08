"""Field complaint #2: dam break onto a dry bed (front position and depth sign).

Run:  python /app/examples/dam_break.py
"""
import sys

import numpy as np

sys.path.insert(0, "/app")

from swe import simulate

nx = 400
dx = 1.0 / nx
x = (np.arange(nx) + 0.5) * dx
h = np.where(x < 0.5, 1.0, 0.0)
row = lambda a: a[None, :]

(h1, hu1, _), = simulate(row(h), row(0 * h), row(0 * h), row(0 * h), dx, 1.0, [0.1], boundary="open")
wet = np.nonzero(h1[0] > 1e-6)[0]
print("min depth        :", h1.min())
print("front position   :", x[wet[-1]] if wet.size else None)
