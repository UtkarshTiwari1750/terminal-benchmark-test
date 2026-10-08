"""Grade the submitted /app/sw calculator.

Every submission call runs in a fresh `python -I` process as UID 65534 with a
time limit. Reference fixtures stay in /tests, which is made root-only before
any submission code runs. Criteria are independent; reward is 1 only if all pass.
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
LOGS = Path("/logs/verifier")
TIME_LIMIT = 300

TOL = {"energy": 1e-7, "forces": 1e-6, "stress": 1e-8, "hessian": 1e-5,
       "scale_energy": 1e-5, "scale_seconds": 60.0, "md_drift": 5e-4, "md_momentum": 1e-9}
WEIGHTS = {"energy": 20, "forces": 20, "stress": 20, "hessian": 25, "scale_dynamics": 15}
SCALE_BASE, SCALE_REPEAT = "sige_64", (5, 5, 5)
MD = {"seed": 12, "temperature": 1200.0, "dt": 1.0, "steps": 300, "potential": "Si.sw"}


class Runner:
    def __init__(self, workdir, log):
        self.workdir, self.log = workdir, log

    def __call__(self, mode, **arrays):
        call = Path(tempfile.mkdtemp(dir=self.workdir))
        src, dst = call / "in.npz", call / "out.npz"
        np.savez(src, **arrays)
        os.chmod(call, 0o755)
        os.chmod(src, 0o644)
        kwargs = {}
        if os.geteuid() == 0:
            os.chown(call, 65534, 65534)
            kwargs = {"user": 65534, "group": 65534, "extra_groups": []}
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(call),
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
               "PYTHONDONTWRITEBYTECODE": "1"}
        self.log.write(f"=== {mode} {arrays.get('name', '')}\n")
        self.log.flush()
        try:
            proc = subprocess.run([sys.executable, "-I", str(self.workdir / "probe.py"), mode, str(src), str(dst)],
                                  cwd=call, env=env, stdout=self.log, stderr=subprocess.STDOUT,
                                  timeout=TIME_LIMIT, **kwargs)
        except subprocess.TimeoutExpired:
            return {"_error": f"exceeded {TIME_LIMIT} s"}
        if proc.returncode or not dst.exists():
            return {"_error": f"probe exited with code {proc.returncode}"}
        with np.load(dst, allow_pickle=False) as data:
            return {k: data[k] for k in data.files}


def structure_args(ref):
    return {k: ref[k] for k in ("numbers", "positions", "cell", "pbc", "potential")}


def max_err(got, want):
    got = np.asarray(got, float)
    if got.shape != np.shape(want):
        return math.inf, f"shape {got.shape}, expected {np.shape(want)}"
    if not np.all(np.isfinite(got)):
        return math.inf, "non-finite values"
    return float(np.max(np.abs(got - want))) if got.size else 0.0, None


def compare(result, key, want, tol):
    if "_error" in result:
        return {"pass": False, "error": result["_error"]}
    if key not in result:
        msg = str(result.get(key + "_error", "missing"))
        return {"pass": False, "error": msg.strip().splitlines()[-1] if msg.strip() else "missing"}
    err, why = max_err(result[key], want)
    return {"pass": err <= tol, "max_error": err, "tolerance": tol, **({"error": why} if why else {})}


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="sw-grade-"))
    os.chmod(work, 0o755)
    shutil.copy(HERE / "probe.py", work / "probe.py")
    os.chmod(work / "probe.py", 0o644)
    if os.geteuid() == 0:
        os.chmod(HERE, 0o700)   # fixtures unreadable to submission code

    refs = {p.stem: dict(np.load(p, allow_pickle=False)) for p in sorted(FIX.glob("*.npz"))}
    details = {g: {} for g in WEIGHTS}
    with open(LOGS / "probe-output.log", "w") as log:
        run = Runner(work, log)
        for name, ref in refs.items():
            res = run("efs", name=np.array(name), **structure_args(ref))
            details["energy"][name] = compare(res, "energy", ref["energy"], TOL["energy"])
            details["forces"][name] = compare(res, "forces", ref["forces"], TOL["forces"])
            if "stress" in ref:
                details["stress"][name] = compare(res, "stress", ref["stress"], TOL["stress"])
            if "hessian" in ref:
                res = run("hessian", name=np.array(name), **structure_args(ref))
                details["hessian"][name] = compare(res, "hessian", ref["hessian"], TOL["hessian"])

        base = refs[SCALE_BASE]
        res = run("scale", name=np.array("scale"), repeat=np.array(SCALE_REPEAT), **structure_args(base))
        copies = int(np.prod(SCALE_REPEAT))
        sc = {"energy": compare(res, "energy", copies * base["energy"], TOL["scale_energy"]),
              "forces": compare(res, "forces", np.tile(base["forces"], (copies, 1)), TOL["forces"]),
              "stress": compare(res, "stress", base["stress"], TOL["stress"])}
        seconds = float(res.get("seconds", math.inf)) if "_error" not in res else math.inf
        sc["time"] = {"pass": seconds <= TOL["scale_seconds"], "seconds": seconds, "limit": TOL["scale_seconds"]}
        details["scale_dynamics"]["scale"] = {"pass": all(v["pass"] for v in sc.values()), "parts": sc}

        res = run("md", name=np.array("md"), **{k: np.array(v) for k, v in MD.items()})
        if "total_energy" in res and np.all(np.isfinite(res["total_energy"])):
            e = res["total_energy"]
            drift = float(np.max(np.abs(e - e[0])) / int(res["natoms"]))
            mom = float(np.max(res["momentum"]))
            details["scale_dynamics"]["md"] = {
                "pass": drift <= TOL["md_drift"] and mom <= TOL["md_momentum"],
                "max_drift_per_atom": drift, "max_momentum": mom,
                "tolerances": [TOL["md_drift"], TOL["md_momentum"]]}
        else:
            details["scale_dynamics"]["md"] = {"pass": False, "error": str(res.get("_error", res.get("total_energy_error", "non-finite")))[-500:]}

    outcomes = {g: int(bool(details[g]) and all(c["pass"] for c in details[g].values())) for g in WEIGHTS}
    reward = int(all(outcomes.values()))
    report = {"reward": reward,
              "weighted_score": sum(WEIGHTS[g] * outcomes[g] for g in WEIGHTS) / 100,
              "per_criterion": outcomes, "weights": WEIGHTS, "details": details}
    (LOGS / "criteria.json").write_text(json.dumps(report, indent=2, default=str))
    (LOGS / "reward.txt").write_text(str(reward))
    print(json.dumps({k: report[k] for k in ("reward", "weighted_score", "per_criterion")}, indent=2))


if __name__ == "__main__":
    main()
