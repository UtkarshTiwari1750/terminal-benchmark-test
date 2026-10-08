# Shallow-water wetting and drying

**Domain:** scientific computing (numerical PDEs / hydraulics)
**Format:** Harbor task, `task.toml` schema 1.4 (validated with Harbor 0.24.0's own `TaskConfig` loader)

The agent receives a working but naive 2D shallow-water flood solver (`/app/swe`). It is first-order, its bed-slope source term is not balanced against the pressure flux, and it has no wet/dry treatment. The agent must make the same `simulate` API produce a solver that is, *at the same time*:

- **well-balanced**: still water over arbitrary terrain stays exactly still, including dry islands and half-flooded cells;
- **positivity-preserving**: depth never goes negative at moving shorelines or dam breaks onto dry land;
- **second-order accurate**: measured by grid refinement on smooth flow over a non-flat bed;
- **conservative and fast**: mass is conserved to round-off, and a 256×256 grid finishes in time.

Each property alone is textbook material. The difficulty is that the standard fixes interact. Second-order reconstruction breaks well-balancing unless it is done on the right variables. Bed-slope source terms at faces must stay consistent with positivity clipping. Velocity must be recovered from vanishing depths without blow-ups. Time stepping must keep positivity *and* second order, and still hit the requested output times exactly. A partial solution reliably fails a specific criterion, and the instruction states every threshold but no method.

## Layout

```
instruction.md          agent prompt (565 words by wc; 583 whitespace tokens)
task.toml               Harbor config: 2 CPU, 4 GB; agent may reach only api.anthropic.com, verifier offline; 4 h / 40 min
environment/
  Dockerfile            digest-pinned python:3.12.11-slim-bookworm, pinned numpy/scipy/matplotlib/pytest
  app/swe/              legacy solver the agent must fix (public API: swe.simulate)
  app/examples/         two scripts reproducing the field complaints
solution/
  solve.sh              oracle: installs the reference solver
  oracle_solver.py      MUSCL + hydrostatic reconstruction + HLL + SSP-RK2 (≈200 lines)
tests/
  test.sh               entry point; writes /logs/verifier/reward.txt
  grade.py              runs each case, applies thresholds, writes criteria.json
  cases.py              problem set and analytic references (Stoker, Ritter, Thacker 1D/2D)
  probe.py              isolated runner: only .npz arrays cross the process boundary
evidence/               calibration results + template for model rollouts
```

## Verification design

| Criterion | Weight | Cases | Reference |
|---|---:|---|---|
| Well-balanced | 20 | lake with islands, 1D + 2D | invariant: zero motion within 1e-11 |
| Dam breaks | 20 | wet Stoker; dry Ritter along x and along y | exact Riemann solutions |
| Second order | 20 | 5-grid self-convergence, smooth periodic flow over a bed | observed order ≥ 1.8 |
| Moving shorelines | 25 | Thacker parabolic bowl, 1D (full period) + 2D | exact analytic solution |
| Scale | 15 | 2D Thacker on 256² within 120 s | exact analytic solution + time |

- References are analytic or invariant-based. None is produced by the oracle; the oracle is only used to calibrate tolerances (about 2–3× its error).
- The submission never shares an interpreter with the references. Each `simulate` call runs in a fresh `python -I` process as UID 65534, single-threaded, with a 300 s limit, and only `numpy` arrays are exchanged (`allow_pickle=False`).
- The reward is binary: 1 only if all five criteria pass. `criteria.json` records per-criterion outcomes, every metric and a weighted diagnostic score.

## Calibration (run locally by the author)

Solvers graded with the exact verifier:

| Solver | Well-bal. | Dam break | 2nd order | Shoreline | Scale | Weighted |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Shipped legacy solver | ✗ | ✗ | ✗ | ✗ | ✗ | 0.00 |
| First-order, well-balanced, positive | ✓ | ✗ | ✗ | ✗ | ✗ | 0.20 |
| Second-order, not well-balanced | ✗ | ✓ | ✗ | ✗ | ✗ | 0.20 |
| Oracle with forward-Euler time stepping | ✓ | ✗ | ✗ | ✗ | ✓ | 0.35 |
| **Oracle** (5 consecutive runs) | ✓ | ✓ | ✓ | ✓ | ✓ | **1.00 ×5** |

Each plausible shortcut fails a *different* criterion, so partial solutions spread out rather than cluster. Oracle verifier time is about 32 s on two cores, and the scale case takes about 20 s against its 120 s budget. The oracle also passes under the pinned `numpy==2.1.3`.

Oracle metrics (tolerance in brackets): lake momentum 2e-15 [1e-11]; Stoker L1 depth 1.3e-3 [2.5e-3]; Ritter 9.8e-4 [2e-3]; observed orders 1.96/1.96/1.96 [≥1.8]; Thacker-1D 2.1e-4 [6e-4]; Thacker-2D 2.8e-3 [5e-3]; scale 4.6e-4 [1e-3].

## Running

```sh
harbor run -p ./shallow-water-wetdry -a oracle -k 5 -n 1          # must be 5/5
harbor run -p ./shallow-water-wetdry -a nop                         # must be 0
harbor run -p ./shallow-water-wetdry -a claude-code -m <model> -k 5 -n 1
```

## Status

- Oracle 5/5 and starter 0/1 were verified by running `tests/test.sh` in a simulated container layout (`/app`, `/tests`, `/solution`, `/logs`) as root with unprivileged probes. **The Docker image itself has not yet been built by the author**, because the authoring machine could not reach Docker Hub. Run the oracle command above before submitting.
- Model rollouts are recorded in `evidence/rollouts.md`.
