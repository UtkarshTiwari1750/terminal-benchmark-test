# Scientific-computing benchmark tasks (Harbor / Terminal-Bench 2 format)

Two tasks in the science domain, each built so that a frontier coding agent has to do real numerical and scientific reasoning over many steps. Each is graded by independent, deterministic checks against references that do not come from the oracle.

| Task | What the agent must do | Graded on (weight) |
|---|---|---|
| [`sw-calculator/`](sw-calculator/) **(primary)** | Turn a broken ASE calculator for the Stillinger–Weber three-body potential into a correct implementation: multi-element LAMMPS `.sw` files, every periodic image in small and skewed cells (including an atom's own images), and analytic forces, stress and full Hessian, fast enough for 8,000 atoms. | Energy 20 · Forces 20 · Stress 20 · Hessian 25 · Scale + MD 15 |
| [`shallow-water-wetdry/`](shallow-water-wetdry/) | Make a 2D finite-volume shallow-water solver well-balanced (still water stays still over any terrain), positivity-preserving at moving shorelines, second-order accurate and fast. | Well-balanced 20 · Dam breaks 20 · 2nd order 20 · Moving shorelines 25 · Scale 15 |

Each task folder has its own README with the full design, verification details and calibration.

## Repository layout

```
<task>/
  instruction.md          prompt shown to the agent (≤ 600 words)
  task.toml               Harbor config: resources, timeouts, network policy
  environment/            Dockerfile + the starting code the agent works on (/app)
  solution/               oracle (solve.sh) — used only by the oracle agent
  tests/                  hidden verifier: test.sh → grade.py, isolated probe, reference fixtures
  reference/              (sw-calculator) author tooling that regenerates the fixtures independently
  evidence/               oracle/nop results and the rollout table
qa/                       Task QA Runbook v2 tooling configured for this repo (see qa/README.md)
```

## Design principles (both tasks)

- **Real libraries, pinned and offline.** The base image is pinned by digest and every Python package by version. During the agent phase only the model API (`api.anthropic.com`) is reachable, and the verifier has no network at all.
- **Independent references.** Shallow water uses exact solutions (Stoker and Ritter dam breaks, Thacker's oscillating bowl) and invariants. Stillinger–Weber uses a brute-force image-sum energy, with exact complex-step derivatives.
- **Behaviour, not strings.** Every check compares numbers within tolerances stated in the instruction.
- **Hard to game.** The agent's code runs as an unprivileged user in a fresh `python -I` process for each call, and only arrays cross the process boundary. Reference fixtures are made root-only before any submission code runs.
- **Spread-out partial scores.** Five independent criteria. Plausible half-correct solutions score between 0.00 and 0.75, and each fails a different criterion.
- **Tolerances that accept other valid methods.** Two alternative shallow-water schemes (Rusanov flux; MC limiter) pass every threshold. Stillinger–Weber tolerances are 10²–10⁷ times looser than round-off differences between valid implementations.

## Running

Requires Docker and [Harbor](https://github.com/laude-institute/harbor) (`uv tool install harbor`). Run from the repository root:

```sh
harbor run -p ./sw-calculator -a oracle -k 5 -n 1        # expect 5/5 reward 1
harbor run -p ./sw-calculator -a nop                      # expect reward 0
harbor run -p ./sw-calculator -a claude-code -m anthropic/claude-opus-5 -k 5 -n 1 --env-file .env
```

Swap `sw-calculator` for `shallow-water-wetdry` to run the other task. `.env` must contain `ANTHROPIC_API_KEY`, and is ignored by git.

## Status

| Check | sw-calculator | shallow-water-wetdry |
|---|---|---|
| Oracle, 5 runs (Harbor, Docker) | ✅ 5/5, mean 1.000 | ✅ 5/5, mean 1.000 |
| Empty attempt (`nop`) | ✅ 0.000 | ✅ 0.000 |
| `instruction.md` ≤ 600 words | ✅ 435 | ✅ 565 |
| Calibration: partial solutions spread across criteria | ✅ 0.00 / 0.60 / 0.65 / 0.75 | ✅ 0.20 / 0.20 / 0.35 |
| QA Runbook pre-rollout check | see `qa-output/preflight/` | see `qa-output/preflight/` |
| 5 model rollouts (Opus 5 / GPT-5.6) | ⏳ pending API credit | ⏳ pending API credit |

The Claude Code agent runs correctly in this harness. The model rollouts are blocked only by API billing on the author's account. Once they run, each task's `evidence/rollouts.md` records per-rollout reward, per-criterion outcomes, step counts and failure notes, generated with `qa/harbor_to_rollouts.py`.
