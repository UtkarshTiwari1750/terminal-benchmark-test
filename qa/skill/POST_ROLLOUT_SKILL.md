---
name: task-quality-postrun
description: "Run post-rollout QA from task-level rollout results; identify repeated zero-pass criteria, assign root causes, and produce an HTML report."
---
# Post-Rollout Task QA

<!-- Body transcribed from "Task QA Runbook v2", Appendix C. Only the Configuration values are filled in
     for this repository; install_skill.sh replaces __REPO__ and __SKILL_DIR__ with absolute paths. -->

## Configuration
ROLLOUTS = __REPO__/qa-output/rollouts.jsonl (produced from Harbor job folders by __REPO__/qa/harbor_to_rollouts.py; per-trial grader evidence is in <task>/jobs/<job>/<trial>/verifier/criteria.json and agent logs in .../agent/)
DATA_DIR = __REPO__
OUTPUT_DIR = __REPO__/qa-output/postrun
SKILL_DIR = __SKILL_DIR__

## Rollout input
`ROLLOUTS` must contain one JSON object per task/sample:
```json
{"task_id":"<stable id matching DATA_DIR>","model":"<model/run label>","reward":0.73,"per_criterion":{"1":1,"2":0,"3":1}}
```
`reward` is the task-level score (0-1). `per_criterion` maps each rubric number to its criterion outcome, where `0` means not passed and a positive value means passed/scored. Emit one row per task/sample. Convert other grader output formats to this schema before running the analysis.

## 1. Aggregate results
```bash
python3 <SKILL_DIR>/dq_post.py stats --rollouts <ROLLOUTS> --output-dir <OUTPUT_DIR>
```
This creates `post_summary.jsonl` plus one `rca_input_NNN.json` for each task with at least one criterion that received a zero outcome in every reported sample.

## 2. Review repeated zero-pass criteria
Use one independent reviewer/subagent per `rca_input_NNN.json`.

### RCA reviewer prompt
Read `<OUTPUT_DIR>/rca_input_NNN.json` and locate the matching task under `DATA_DIR`. For every entry in `zero_pass_criteria`, read the corresponding grading criterion and inspect the actual task inputs plus any grader/output evidence available for that rollout.

Assign exactly one `primary_issue` based on direct evidence:
- `GENUINE_FAILURE`: the task is solvable and the grading criterion is valid; the rollout outputs did not satisfy it.
- `RUBRIC_INACCURATE`: the criterion contains an expected value, ID, count, fact, or requirement that conflicts with the actual task data.
- `RUBRIC_DESIGN`: the criterion is not reliably evaluable, is arbitrarily over-specific, or has the wrong weight direction.
- `DATA_ISSUE`: data required by the criterion is missing, incorrect, or contradictory in the runtime inputs.
- `GRADER_FALSE_POSITIVE`: a correct/valid output can be rejected by the grading implementation.
- `GRADER_TRUNCATION`: the available rollout evidence shows the output was cut off before the grader could evaluate the relevant content.

Verify against the real task data and available grading evidence; do not infer the root cause from failure frequency alone.

Write `<OUTPUT_DIR>/rca_verdict_NNN.json`:
```json
{"task_id":"<id>","criteria_rca":[{"criterion_key":"<rubric number>","primary_issue":"<label above>","evidence":"<brief evidence>"}],"task_level_assessment":"<one-line summary>"}
```

## 3. Build the report
`python3 <SKILL_DIR>/dq_post.py report --output-dir <OUTPUT_DIR> --output <OUTPUT_DIR>/post_report.html`
