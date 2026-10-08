"""Grade the submitted /app/swe package.

Every case runs in a fresh subprocess (unprivileged when possible) with a
time limit. Criteria are independent; the reward is 1 only if all pass.
A weighted diagnostic score is written to criteria.json.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGS = Path("/logs/verifier")
TIME_LIMIT = 300

WEIGHTS = {"well_balanced": 20, "dam_break": 20, "convergence": 20,
           "moving_shoreline": 25, "scale": 15}
GROUPS = {"well_balanced": ["lake_1d", "lake_2d"],
          "dam_break": ["stoker_x", "ritter_x", "ritter_y"],
          "convergence": ["convergence"],
          "moving_shoreline": ["thacker_1d", "thacker_2d"],
          "scale": ["performance"]}


def le(value, limit, label):
    if not (isinstance(value, (int, float)) and math.isfinite(value) and value <= limit):
        raise AssertionError(f"{label} = {value!r}, limit {limit}")


def ge(value, limit, label):
    if not (isinstance(value, (int, float)) and math.isfinite(value) and value >= limit):
        raise AssertionError(f"{label} = {value!r}, required >= {limit}")


def basic(m):
    if m.get("finite") is not True:
        raise AssertionError("non-finite values in output")
    if "min_depth" in m:
        ge(m["min_depth"], 0.0, "minimum depth")


def check(name, m):
    basic(m)
    if name in ("lake_1d", "lake_2d"):
        le(m["max_momentum"], 1e-11, "max |hu|+|hv|")
        le(m["max_depth_change"], 1e-11, "max depth change")
    elif name == "stoker_x":
        le(m["l1_depth"], 2.5e-3, "L1 depth error")
        le(m["l1_discharge"], 6e-3, "L1 discharge error")
    elif name in ("ritter_x", "ritter_y"):
        le(m["l1_depth"], 2e-3, "L1 depth error")
        le(m["l1_discharge"], 4.5e-3, "L1 discharge error")
        le(m["max_tangential"], 1e-12, "tangential discharge")
    elif name == "convergence":
        for i, order in enumerate(m["orders"]):
            ge(order, 1.8, f"observed order {i}")
        le(m["mass_spread"], 1e-12, "mass spread")
    elif name == "thacker_1d":
        le(m["l1_depth"], 6e-4, "L1 depth error")
        le(m["l1_discharge"], 1e-3, "L1 discharge error")
        le(m["relative_mass_error"], 1e-12, "relative mass error")
    elif name == "thacker_2d":
        le(m["l1_depth"], 5e-3, "L1 depth error")
        le(m["l1_discharge"], 9e-3, "L1 discharge error")
        le(m["mirror_asymmetry"], 1e-10, "mirror asymmetry")
        le(m["relative_mass_error"], 1e-12, "relative mass error")
    elif name == "performance":
        le(m["seconds"], 120.0, "solve seconds")
        le(m["l1_depth"], 1e-3, "L1 depth error")
        le(m["relative_mass_error"], 1e-12, "relative mass error")


class Isolated:
    """Callable with simulate()'s signature that runs the submission in a subprocess."""

    def __init__(self, workdir, log):
        self.workdir, self.log, self.calls = workdir, log, 0

    def __call__(self, h, hu, hv, z, dx, dy, times, g=9.81, boundary="wall"):
        import numpy as np
        self.calls += 1
        call_dir = Path(tempfile.mkdtemp(dir=self.workdir))
        source, target = call_dir / "in.npz", call_dir / "out.npz"
        np.savez(source, h=h, hu=hu, hv=hv, z=z, dx=dx, dy=dy, times=np.asarray(times, float),
                 g=g, boundary=np.asarray(boundary))
        os.chmod(call_dir, 0o755)
        os.chmod(source, 0o644)
        kwargs = {}
        if os.geteuid() == 0:
            os.chown(call_dir, 65534, 65534)
            kwargs = {"user": 65534, "group": 65534, "extra_groups": []}
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(call_dir),
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run([sys.executable, "-I", str(self.workdir / "probe.py"), str(source), str(target)],
                              cwd=call_dir, env=env, stdout=self.log, stderr=subprocess.STDOUT,
                              timeout=TIME_LIMIT, **kwargs)
        if proc.returncode:
            raise AssertionError(f"submission exited with code {proc.returncode}")
        with np.load(target, allow_pickle=False) as data:
            count = int(data["count"])
            return [(data[f"h{i}"], data[f"hu{i}"], data[f"hv{i}"]) for i in range(count)]


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="swe-grade-"))
    os.chmod(work, 0o755)
    shutil.copy(HERE / "probe.py", work / "probe.py")
    os.chmod(work / "probe.py", 0o644)
    sys.path.insert(0, str(HERE))
    import cases

    outcomes, details = {}, {}
    with open(LOGS / "probe-output.log", "w") as log:
        for group, names in GROUPS.items():
            details[group] = {}
            ok = True
            for name in names:
                try:
                    log.write(f"=== {name}\n")
                    log.flush()
                    metrics = cases.CASES[name](Isolated(work, log))
                    check(name, metrics)
                    details[group][name] = {"pass": True, "metrics": metrics}
                except subprocess.TimeoutExpired:
                    ok = False
                    details[group][name] = {"pass": False, "error": f"exceeded {TIME_LIMIT} s"}
                except Exception as error:  # noqa: BLE001 - every failure is a failed case
                    ok = False
                    details[group][name] = {"pass": False, "error": f"{type(error).__name__}: {error}"}
            outcomes[group] = int(ok)

    reward = int(all(outcomes.values()))
    report = {"reward": reward,
              "weighted_score": sum(WEIGHTS[g] * outcomes[g] for g in outcomes) / 100,
              "per_criterion": outcomes, "weights": WEIGHTS, "details": details}
    (LOGS / "criteria.json").write_text(json.dumps(report, indent=2, default=str))
    (LOGS / "reward.txt").write_text(str(reward))
    print(json.dumps({k: report[k] for k in ("reward", "weighted_score", "per_criterion")}, indent=2))


if __name__ == "__main__":
    main()
