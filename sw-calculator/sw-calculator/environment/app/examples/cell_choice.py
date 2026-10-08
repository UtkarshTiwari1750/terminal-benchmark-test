"""Bug report: energy per atom of perfect diamond silicon depends on the cell used.

The 2-atom primitive cell and the 8-atom cubic cell describe the same crystal,
so energy per atom must agree (about -4.3366 eV/atom for these parameters).

Run:  python /app/examples/cell_choice.py
"""
import sys

sys.path.insert(0, "/app")

from ase.build import bulk  # noqa: E402

from sw import StillingerWeber  # noqa: E402

for label, atoms in [("primitive (2 atoms)", bulk("Si", "diamond", a=5.431)),
                     ("cubic (8 atoms)", bulk("Si", "diamond", a=5.431, cubic=True))]:
    atoms.calc = StillingerWeber("/app/potentials/Si.sw")
    print(f"{label:22s} {atoms.get_potential_energy() / len(atoms): .6f} eV/atom")
