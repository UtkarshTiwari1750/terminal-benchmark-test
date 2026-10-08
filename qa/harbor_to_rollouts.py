#!/usr/bin/env python3
"""Convert Harbor job folders into the rollout JSONL that the QA runbook's dq_post.py expects.

One output row per completed trial:
  {"task_id": "<task folder name>", "model": "<model>", "reward": <0..1>,
   "per_criterion": {"1": 0|1, ...}, "binary_reward": 0|1, "steps": <int|null>, "trial": "<trial dir>"}

Criterion numbers follow qa/rubrics/<task>.json, which mirror the numbered list in each
task's instruction.md and the WEIGHTS order in tests/grade.py.

Trials that crashed before grading (no verifier/criteria.json) are not model failures; they are
listed on stderr and skipped. Stdlib only.

Usage:
  python3 qa/harbor_to_rollouts.py --tasks-root . --out qa-output/rollouts.jsonl \
      sw-calculator/jobs/<job> shallow-water-wetdry/jobs/<job> [--reward weighted|binary] [--markdown]
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent


def task_index(tasks_root: Path) -> dict[str, str]:
    """Map every name a trial may report (task.toml name, folder name) to the folder name."""
    index = {}
    for toml in tasks_root.glob("*/task.toml"):
        folder = toml.parent.name
        index[folder] = folder
        try:
            name = tomllib.loads(toml.read_text()).get("task", {}).get("name")
        except tomllib.TOMLDecodeError:
            name = None
        if name:
            index[name] = folder
            index[name.split("/")[-1]] = folder
    return index


def rubric_keys(task: str) -> list[str]:
    path = HERE / "rubrics" / f"{task}.json"
    rubric = json.loads(path.read_text())
    return [r["key"] for r in sorted(rubric, key=lambda r: r["number"])]


def count_steps(agent_dir: Path) -> int | None:
    """Agent actions: tool calls in the Claude Code stream, else ATIF trajectory steps."""
    stream = agent_dir / "claude-code.txt"
    if stream.exists():
        calls = 0
        for line in stream.read_text(errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "assistant":
                content = (event.get("message") or {}).get("content") or []
                calls += sum(1 for block in content if isinstance(block, dict) and block.get("type") == "tool_use")
        return calls
    trajectory = agent_dir / "trajectory.json"
    if trajectory.exists():
        try:
            data = json.loads(trajectory.read_text())
            steps = data.get("steps") if isinstance(data, dict) else None
            return len(steps) if isinstance(steps, list) else None
        except json.JSONDecodeError:
            return None
    return None


def model_of(result: dict) -> str:
    info = (result.get("agent_info") or {}).get("model_info") or {}
    name = info.get("name")
    if name:
        provider = info.get("provider")
        return f"{provider}/{name}" if provider else name
    agent = ((result.get("config") or {}).get("agent") or {})
    return agent.get("model_name") or (result.get("agent_info") or {}).get("name") or "unknown"


def trials(job_dirs: list[Path]):
    for job in job_dirs:
        for result_path in sorted(job.glob("*/result.json")):
            yield result_path.parent, json.loads(result_path.read_text())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs", nargs="+", type=Path, help="Harbor job directories (jobs/<timestamp>)")
    ap.add_argument("--tasks-root", type=Path, default=Path("."), help="folder that contains the task folders")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reward", choices=["weighted", "binary"], default="weighted",
                    help="value written to 'reward': weighted criterion score (default) or Harbor's binary reward")
    ap.add_argument("--markdown", action="store_true", help="also print a table for evidence/rollouts.md")
    args = ap.parse_args()

    index = task_index(args.tasks_root)
    rows, skipped = [], []
    for trial_dir, result in trials(args.jobs):
        task = index.get(result.get("task_name", ""), result.get("task_name", ""))
        criteria_path = trial_dir / "verifier" / "criteria.json"
        if not criteria_path.exists():
            exc = (result.get("exception_info") or {}).get("exception_type", "no criteria.json")
            skipped.append(f"{trial_dir.name} ({task}): {exc}")
            continue
        criteria = json.loads(criteria_path.read_text())
        per = criteria.get("per_criterion", {})
        keys = rubric_keys(task)
        missing = [k for k in keys if k not in per]
        if missing:
            raise SystemExit(f"{criteria_path}: criteria {missing} not found; rubric and grader disagree")
        rows.append({
            "task_id": task,
            "model": model_of(result),
            "reward": float(criteria.get("weighted_score", 0.0)) if args.reward == "weighted"
            else float(criteria.get("reward", 0)),
            "per_criterion": {str(n): int(per[k]) for n, k in enumerate(keys, start=1)},
            "binary_reward": int(criteria.get("reward", 0)),
            "steps": count_steps(trial_dir / "agent"),
            "trial": trial_dir.name,
        })

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    print(f"wrote {len(rows)} rollouts to {args.out}")
    for line in skipped:
        print(f"skipped (crashed before grading): {line}", file=sys.stderr)

    if args.markdown:
        print("\n| Rollout | Task | Model | Reward | Weighted | C1 | C2 | C3 | C4 | C5 | Steps |")
        print("|---|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|--:|")
        for row in rows:
            marks = " | ".join("✓" if row["per_criterion"][str(n)] else "✗" for n in range(1, 6))
            weighted = row["reward"] if args.reward == "weighted" else "—"
            print(f"| {row['trial']} | {row['task_id']} | {row['model']} | {row['binary_reward']} | "
                  f"{weighted} | {marks} | {row['steps'] if row['steps'] is not None else '?'} |")


if __name__ == "__main__":
    main()
