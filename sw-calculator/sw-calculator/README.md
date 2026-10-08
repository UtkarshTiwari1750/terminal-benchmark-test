# Stillinger–Weber calculator for ASE

**Domain:** scientific computing (atomistic simulation / interatomic potentials)
**Format:** Harbor task, `task.toml` schema 1.4 (validated with Harbor 0.24.0's `TaskConfig` and `Task` loaders)

The agent receives a broken ASE calculator for the Stillinger–Weber (SW) three-body potential, the standard model for silicon. It must become a correct, complete implementation:

- **LAMMPS `.sw` file support for several elements.** The starter rejects valid files whose entries span lines and handles only one element. Mixed-species triplets take parameters from three different entries.
- **Correct periodic images.** The starter uses the minimum-image convention, which is silently wrong whenever a lattice vector is shorter than twice the cutoff. Its 2-atom primitive silicon cell gives −1.08 eV/atom instead of −4.34. Small and skewed cells need every image, including images of an atom interacting with itself.
- **Analytic forces, virial stress and the full Hessian.** The three-body angular term makes the second derivatives long and error-prone. In small cells the Hessian must also net out the terms where an atom interacts with its own images.
- **Speed.** 8000 atoms in under 60 s rules out the starter's finite-difference forces.

The contract (`/app/docs/CONTRACT.md`) defines every quantity exactly. The instruction states what is checked and the tolerances, never the method.

## Layout

```
instruction.md            agent prompt (435 words)
task.toml                 2 CPU, 4 GB; agent may reach only api.anthropic.com, verifier fully offline; 4 h agent / 40 min verifier
environment/
  Dockerfile              digest-pinned python:3.12.11-slim-bookworm; pinned numpy, scipy, ase 3.25.0
  app/sw/                 legacy calculator the agent must fix
  app/potentials/         Si.sw (original SW), Si_mod.sw (non-default exponents), SiGe.sw (8 distinct triplets)
  app/docs/CONTRACT.md    exact specification
  app/examples/           cell_choice.py reproduces the field bug
solution/
  solve.sh, sw/           oracle: vectorised energy, forces, stress, Hessian (~250 lines)
tests/
  test.sh, grade.py       grader: per-criterion results, binary reward, criteria.json
  probe.py                isolated runner for the submission
  fixtures/*.npz          precomputed references for 10 structures
reference/                author tooling, not shipped: independent reference + fixture builder
evidence/                 rollout template
```

## Independent references

`reference/sw_reference.py` evaluates the contract energy by brute force over explicitly enumerated periodic images. It is written to accept complex positions and cells, so:

- forces and stress come from **complex-step differentiation** (exact to round-off; no analytic derivative of the potential appears anywhere);
- the Hessian is a 4th-order central difference of those exact gradients (accuracy about 1e-8 eV/Å², against a 1e-5 tolerance).

The oracle's analytic results agree with these references to 1e-14 (energy, forces, stress) and 1e-8 (Hessian). Its stress also agrees with ASE's own numerical stress to 1e-10, which confirms the sign and Voigt conventions. Rebuild the fixtures with `python reference/build_fixtures.py`.

## Verification design

| Criterion | Weight | What is checked | Tolerance |
|---|---:|---|---|
| Energy | 20 | 10 structures | 1e-7 eV |
| Forces | 20 | 10 structures | 1e-6 eV/Å |
| Stress | 20 | 8 fully periodic structures | 1e-8 eV/Å³ |
| Hessian | 25 | 9 structures ≤ 16 atoms, incl. 1-atom cell, slab, cluster | 1e-5 eV/Å² |
| Scale + dynamics | 15 | 8000-atom tiling invariance within 60 s; 300-step NVE run with wrapping | see instruction |

Structures: rattled diamond; 2-atom primitive triclinic Si; a 1-atom triclinic cell with all lattice vectors shorter than the cutoff; 16 random atoms in a skewed cell with unwrapped positions; a slab periodic in 2D; a 10-atom cluster; Si_mod diamond; SiGe zincblende primitive; random SiGe triclinic; 64-atom SiGe alloy.

The scale check needs no new reference: a 5×5×5 repetition must give exactly 125× the energy, the tiled forces and the same stress. The MD check uses fresh trajectories nobody has seen, so it cannot be passed by fitting fixtures.

Isolation: each call runs in a fresh `python -I` process as UID 65534, single-threaded, with a 300 s limit. `/tests` is made root-only (mode 700) before any submission code runs, and only arrays cross the process boundary (`allow_pickle=False`).

## Calibration (run locally by the author with the exact grader)

| Solver | Energy | Forces | Stress | Hessian | Scale+MD | Weighted |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Shipped legacy calculator | ✗ | ✗ | ✗ | ✗ | ✗ | 0.00 |
| Nearest image only | ✗ | ✗ | ✗ | ✗ | ✗ | 0.00 |
| Three-body λ, cosθ0 taken from the pair entry | ✗ | ✗ | ✗ | ✗ | ✗ | 0.00 |
| Self-image interactions dropped | ✗ | ✓ | ✗ | ✓ | ✓ | 0.60 |
| Stress sign flipped | ✓ | ✓ | ✗ | ✓ | ✗ | 0.65 |
| Hessian missing the h₁/h₂ cross terms | ✓ | ✓ | ✓ | ✗ | ✓ | 0.75 |
| **Oracle** (5 consecutive runs) | ✓ | ✓ | ✓ | ✓ | ✓ | **1.00 ×5** |

Oracle timing: whole verifier about 9 s; 8000-atom E+F+S 0.5 s (limit 60 s); NVE drift 1.1e-4 eV/atom (limit 5e-4). The starter's verifier run takes about 5 min because the scale case times out.

## Running

```sh
harbor run -p ./sw-calculator -a oracle -k 5 -n 1          # must be 5/5
harbor run -p ./sw-calculator -a nop                        # must be 0
harbor run -p ./sw-calculator -a claude-code -m <model> -k 5 -n 1
```

## Status

- The oracle passing 5/5 and the starter scoring 0 were verified by running the grader in a simulated container layout (`/app`, `/tests`, `/solution`, `/logs`) with pinned ASE 3.25.0 and numpy 2.1.3, and unprivileged probes. **The Docker image has not been built by the author yet**, because the authoring machine could not reach Docker Hub. Run the oracle command above before submitting.
- Model rollouts go in `evidence/rollouts.md`.
