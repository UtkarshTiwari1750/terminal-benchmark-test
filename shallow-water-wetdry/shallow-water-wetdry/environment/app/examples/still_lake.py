"""Field complaint #1: a still reservoir over a rough bed starts to flow.

Run:  python /app/examples/still_lake.py
"""
import sys

import numpy as np

sys.path.insert(0, "/app")

from swe import simulate

nx = 200
dx = 1.0 / nx
x = (np.arange(nx) + 0.5) * dx
z = 0.8 * np.exp(-((x - 0.5) / 0.08) ** 2) + 0.15 * np.sin(13 * x) ** 2
h = np.maximum(0.0, 0.6 - z)          # free surface at 0.6, island emerges
row = lambda a: a[None, :]

(h1, hu1, hv1), = simulate(row(h), row(0 * h), row(0 * h), row(z), dx, 1.0, [1.0], boundary="wall")
print("max |hu| after 1 s :", np.abs(hu1).max())
print("min depth          :", h1.min())
print("max depth change   :", np.abs(h1[0] - h).max())
