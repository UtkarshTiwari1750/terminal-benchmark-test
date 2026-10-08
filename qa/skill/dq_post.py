#!/usr/bin/env python3
"""Portable POST-rollout quality helper — stdlib only, no external services.

Consumes YOUR rollout results (a local JSONL — one row per (task, sample)) and produces
per-task reward stats, cross-model zero-pass criteria, RCA dispatch inputs, and a local HTML report.

Rollout input row schema (one JSON object per line):
  {
    "task_id": "<stable id>",              # required
    "model": "<model label>",              # required (>=2 distinct models recommended)
    "reward": 0.73,                        # required, task-level reward for this sample (0..1)
    "per_criterion": {"1": 1, "2": 0, ...} # required: rubric-number -> pass(1)/fail(0) or score
  }

Subcommands:
  stats --rollouts roll.jsonl --output-dir OUT
      Aggregate per task; write OUT/post_summary.jsonl and OUT/rca_input_NNN.json for tasks with
      >=1 cross-model zero-pass criterion; print the reward distribution.
  report --output-dir OUT --output OUT/post_report.html
      Render reward buckets + zero-pass table, folding in OUT/rca_verdict_*.json if present.
"""
from __future__ import annotations
import argparse, glob, json, os, statistics as st, html as html_lib
from collections import defaultdict
from pathlib import Path


def _load_rollouts(path):
    by = defaultdict(list)
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        by[r["task_id"]].append(r)
    return by


def stats(rollouts, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    by = _load_rollouts(rollouts)
    summ = []
    n_rca = 0
    for i, (tid, samples) in enumerate(sorted(by.items())):
        rewards = [float(s.get("reward", 0)) for s in samples]
        models = sorted({s.get("model", "?") for s in samples})
        # cross-model zero-pass: a criterion scored 0 by EVERY sample that reports it
        crit_max = defaultdict(float)
        seen = set()
        for s in samples:
            for k, v in (s.get("per_criterion") or {}).items():
                seen.add(k)
                crit_max[k] = max(crit_max[k], float(v))
        zero_pass = sorted(k for k in seen if crit_max[k] == 0.0)
        row = {"task_id": tid, "models": models, "n_samples": len(samples),
               "avg_reward": round(st.mean(rewards), 4), "min_reward": round(min(rewards), 4),
               "max_reward": round(max(rewards), 4), "n_criteria": len(seen),
               "n_zero_pass": len(zero_pass), "zero_pass_criteria": zero_pass}
        summ.append(row)
        if zero_pass:
            idx = f"{i:03d}"
            Path(f"{out_dir}/rca_input_{idx}.json").write_text(json.dumps(
                {"line_idx": i, "task_id": tid, "zero_pass_criteria": zero_pass,
                 "avg_reward": row["avg_reward"], "min_reward": row["min_reward"]}, indent=2))
            n_rca += 1
    with open(f"{out_dir}/post_summary.jsonl", "w") as f:
        for r in summ:
            f.write(json.dumps(r) + "\n")
    n = max(len(summ), 1)
    avgs = [r["avg_reward"] for r in summ]
    print(f"tasks={len(summ)} models={sorted({m for r in summ for m in r['models']})}")
    print(f"avg_reward mean={st.mean(avgs):.3f} median={st.median(avgs):.3f}")
    print(f"tasks avg<0.5: {sum(a<0.5 for a in avgs)} avg==0: {sum(a==0 for a in avgs)} "
          f"min<0.8: {sum(r['min_reward']<0.8 for r in summ)}")
    tot_c = sum(r["n_criteria"] for r in summ)
    zp = sum(r["n_zero_pass"] for r in summ)
    print(f"cross-model zero-pass criteria: {zp}/{tot_c} tasks w/ >=1: {n_rca}")
    print(f"wrote {out_dir}/post_summary.jsonl and {n_rca} rca_input_*.json")


_STYLE = ("body{font-family:-apple-system,Arial,sans-serif;margin:0;padding:24px;background:#f0f2f5;color:#1c1e21}"
          ".wrap{max-width:1100px;margin:0 auto}h1{font-size:22px;margin:0 0 4px}"
          ".sub{color:#65676b;font-size:13px;margin-bottom:16px}"
          ".card{background:#fff;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,.1);padding:16px 20px;margin-bottom:16px}"
          "h2{font-size:15px;margin:0 0 12px}table{border-collapse:collapse;width:100%;font-size:13px}"
          "th{background:#f8f9fa;text-align:left;padding:9px 11px;border-bottom:2px solid #e4e6eb;font-size:11px;"
          "text-transform:uppercase;color:#65676b}td{padding:8px 11px;border-bottom:1px solid #eef0f2}"
          ".num{text-align:right;font-variant-numeric:tabular-nums}.bar{height:20px;border-radius:4px;display:inline-block}")


def report(out_dir, out_html):
    summ = [json.loads(l) for l in open(f"{out_dir}/post_summary.jsonl") if l.strip()]
    verdicts = {}
    for vf in glob.glob(f"{out_dir}/rca_verdict_*.json"):
        v = json.load(open(vf))
        verdicts[v.get("task_id", "")] = v
    avgs = [r["avg_reward"] for r in summ]
    buckets = [("avg == 0 (broken/unsolvable)", sum(a == 0 for a in avgs), "#e74c3c"),
               ("0 < avg < 0.5 (hard or broken)", sum(0 < a < 0.5 for a in avgs), "#e67e22"),
               ("0.5 <= avg < 0.8 (sweet spot)", sum(0.5 <= a < 0.8 for a in avgs), "#27ae60"),
               ("0.8 <= avg < 1.0 (easy-ish)", sum(0.8 <= a < 1.0 for a in avgs), "#2ecc71"),
               ("avg == 1.0 (saturated)", sum(a == 1.0 for a in avgs), "#f39c12")]
    rc = defaultdict(int)
    for v in verdicts.values():
        for c in v.get("criteria_rca", []):
            rc[c.get("primary_issue", "UNKNOWN")] += 1
    p = [f"<!doctype html><html><head><meta charset='utf-8'><title>Post-Rollout Quality</title>"
         f"<style>{_STYLE}</style></head><body><div class='wrap'>"]
    n = max(len(summ), 1)
    p.append(f"<div class='card'><h1>Post-Rollout Quality Report</h1><div class='sub'>{len(summ)} tasks &bull; "
             f"reward + cross-model zero-pass</div>"
             f"<table><tr><th>Metric</th><th>Value</th></tr>"
             f"<tr><td>Tasks</td><td class='num'>{len(summ)}</td></tr>"
             f"<tr><td>Avg reward (mean / median)</td><td class='num'>{st.mean(avgs):.3f} / {st.median(avgs):.3f}</td></tr>"
             f"<tr><td>Tasks min_reward &lt; 0.8</td><td class='num'>{sum(r['min_reward']<0.8 for r in summ)}</td></tr>"
             f"<tr><td>Cross-model zero-pass criteria</td><td class='num'>{sum(r['n_zero_pass'] for r in summ)} / "
             f"{sum(r['n_criteria'] for r in summ)}</td></tr>"
             f"<tr><td>Tasks with &ge;1 zero-pass</td><td class='num'>{sum(1 for r in summ if r['n_zero_pass']>0)}</td></tr>"
             f"</table></div>")
    mx = max((c for _, c, _ in buckets), default=1) or 1
    p.append("<div class='card'><h2>Reward distribution (avg across models)</h2>"
             "<table><tr><th>Bucket</th><th>Tasks</th><th></th></tr>")
    for lab, c, col in buckets:
        p.append(f"<tr><td>{lab}</td><td class='num'>{c}</td><td><span class='bar' "
                 f"style='width:{int(500*c/mx)}px;background:{col}'></span></td></tr>")
    p.append("</table></div>")
    if rc:
        p.append("<div class='card'><h2>RCA root-cause breakdown (zero-pass criteria)</h2>"
                 "<table><tr><th>Primary issue</th><th>Count</th></tr>")
        for k, c in sorted(rc.items(), key=lambda x: -x[1]):
            p.append(f"<tr><td>{html_lib.escape(k)}</td><td class='num'>{c}</td></tr>")
        p.append("</table></div>")
    p.append("<div class='card'><h2>Tasks with zero-pass criteria</h2><table><tr><th>task_id</th><th>avg</th>"
             "<th>min</th><th>zero-pass</th><th>RCA</th></tr>")
    for r in sorted(summ, key=lambda x: (-x["n_zero_pass"], x["avg_reward"])):
        if r["n_zero_pass"] == 0:
            continue
        v = verdicts.get(r["task_id"], {})
        issues = ", ".join(c.get("primary_issue", "") for c in v.get("criteria_rca", [])) if v else ""
        p.append(f"<tr><td>{html_lib.escape(r['task_id'])}</td><td class='num'>{r['avg_reward']:.2f}</td>"
                 f"<td class='num'>{r['min_reward']:.2f}</td>"
                 f"<td class='num'>{r['n_zero_pass']}/{r['n_criteria']}</td><td>{html_lib.escape(issues)}</td></tr>")
    p.append("</table></div></div></body></html>")
    Path(out_html).write_text("".join(p))
    print(f"HTML: {out_html}")


def main():
    ap = argparse.ArgumentParser(description="Portable post-rollout quality helper (stdlib only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stats")
    s.add_argument("--rollouts", required=True)
    s.add_argument("--output-dir", required=True)
    r = sub.add_parser("report")
    r.add_argument("--output-dir", required=True)
    r.add_argument("--output", required=True)
    a = ap.parse_args()
    if a.cmd == "stats":
        stats(a.rollouts, a.output_dir)
    else:
        report(a.output_dir, a.output)


if __name__ == "__main__":
    main()
