`/app/sw` provides a Stillinger–Weber interatomic potential as an ASE calculator, `sw.StillingerWeber(path)`, reading LAMMPS-format `.sw` parameter files from `/app/potentials`. It is not fit for use: it rejects valid parameter files, supports one element only, gives energies that depend on which periodic cell describes the same crystal (`/app/examples/cell_choice.py`), uses slow finite-difference forces, and has no stress or Hessian.

Make it correct and complete. The exact definitions of the parameter-file format, energy, forces, stress (ASE convention) and Hessian are in `/app/docs/CONTRACT.md`; that file is the specification. Keep the public API: `from sw import StillingerWeber`, the constructor taking a path to a `.sw` file, the standard ASE `get_potential_energy`, `get_forces` and `get_stress`, and `calc.get_hessian(atoms)` returning a dense (3N, 3N) array. Your code must stay in `/app/sw`, importable from `/app`, using only the installed packages (Python 3.12, NumPy, SciPy, ASE 3.25.0). Do not change files in `/app/potentials` or `/app/docs`.

## What is verified

Each check runs in a fresh process as an unprivileged user, single-threaded, using `/app/potentials/Si.sw`, `Si_mod.sw` and `SiGe.sw`. References come from an independent brute-force evaluation of the energy in `CONTRACT.md` with explicitly enumerated periodic images; derivatives are taken by complex-step and high-order finite differences of that energy, not from any analytic formula.

Test structures include: perturbed diamond and zincblende cells; two-atom primitive cells and a one-atom cell whose lattice vectors are shorter than the cutoff (so atoms interact with several images of the same atom, including their own); skewed triclinic cells with random atom positions, some given outside the cell; a slab periodic in two directions; an isolated cluster; and Si–Ge structures with distinct parameters for every element triple. A calculator instance is reused across structures.

1. **Energy (20%).** All structures: |E − E_ref| ≤ 1e-7 eV.
2. **Forces (20%).** All structures: every component within 1e-6 eV/Å.
3. **Stress (20%).** All fully periodic structures: every Voigt component within 1e-8 eV/Å³.
4. **Hessian (25%).** All structures up to 16 atoms (including the slab, cluster and one-atom cell): shape (3N, 3N), every entry within 1e-5 eV/Å².
5. **Scale and dynamics (15%).** (a) A 64-atom Si–Ge triclinic cell repeated 5×5×5 (8000 atoms): energy, forces and stress together within 60 s of wall time; energy within 1e-5 eV of 125× the reference for the 64-atom cell, forces within 1e-6 eV/Å and stress within 1e-8 eV/Å³ of the 64-atom reference values. (b) 300 velocity-Verlet steps of 1 fs for 64 silicon atoms starting near 1200 K, wrapping atoms into the cell every step: total energy stays within 5e-4 eV/atom of its initial value and total momentum stays below 1e-9 amu·Å/fs.

Each call has a 300 s limit. Criteria are reported separately; full credit requires all five.
