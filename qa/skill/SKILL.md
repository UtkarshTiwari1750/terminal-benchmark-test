---
name: task-quality-preflight
description: "Run pre-rollout QA on task prompts, grading criteria, tests, and runtime inputs; produce JSONL findings and an HTML report."
---
# Pre-Rollout Task QA

<!-- Body transcribed from "Task QA Runbook v2", Appendix A. Only the Configuration values are filled in
     for this repository; install_skill.sh replaces __REPO__ and __SKILL_DIR__ with absolute paths. -->

## Configuration
DATA_DIR = __REPO__
OUTPUT_DIR = __REPO__/qa-output/preflight
SKILL_DIR = __SKILL_DIR__
PROMPT = <task>/instruction.md, for every folder in DATA_DIR that contains a task.toml (sw-calculator, shallow-water-wetdry). task_id and task_name = the folder name.
RUBRIC = __REPO__/qa/rubrics/<task>.json — use `number`, `points` and `criterion` (`key` is the grader's internal name). These mirror the numbered "What is verified" list in instruction.md and WEIGHTS in tests/grade.py.
TESTS = <task>/tests/: test_code = grade.py followed by the helpers it runs (shallow-water-wetdry: cases.py and probe.py; sw-calculator: probe.py); test_sh = tests/test.sh. Criteria are graded by check functions in grade.py, not pytest `def test_` functions, so use `{}` for test_weights.
INPUTS = <task>/environment/: Dockerfile and requirements.txt define the runtime image; environment/app/ is the agent's /app (sw-calculator also exposes /app/docs/CONTRACT.md, which the prompt names as the specification, plus /app/potentials and /app/examples). The agent can reach only the model API; the verifier runs offline.
IGNORE = <task>/solution/, <task>/reference/, <task>/tests/fixtures/, <task>/evidence/, <task>/jobs/, __REPO__/qa-output/

## 1. Build one review record per task
For each task, write `OUTPUT_DIR/batch_NNN.json` as a one-element JSON array. Use a stable task order and a zero-padded index (`000`, `001`, ...).
```json
[{"task_id":"<stable id>","task_name":"<display name>","task_dir":"<absolute task directory>","prompt_text":"<full prompt>","rubrics":[{"number":1,"points":10,"criterion":"<full grading criterion>"}],"test_code":"<test source or empty string>","test_sh":"<test shell source or empty string>","test_weights":{},"ignore_paths":["<absolute path not visible at runtime>"]}]
```
Normalize each grading criterion to `{number, points, criterion}`. `number` is the criterion index; `points` is its weight; `criterion` must contain the complete criterion, including any sub-criteria and deterministic expected values that need to be checked against the task inputs.
Resolve `IGNORE` into `ignore_paths` for each task so the reviewer knows exactly which paths are off limits.
If there are no mechanical tests, use empty strings for `test_code` and `test_sh` and `{}` for `test_weights`. Confirm `prompt_text` and `rubrics` are populated before review.

## 2. Review each task
Use one independent reviewer/subagent per `batch_NNN.json`. Each reviewer writes `OUTPUT_DIR/verdict_NNN.json`.

### Reviewer prompt
Read `<SKILL_DIR>/eval_guide.md` and follow its decision rules and exact output schema.
Read `<OUTPUT_DIR>/batch_NNN.json`.
1. Inspect the prompt and all inputs/resources the task makes available at runtime. Validate data through the same interface, filtering, and scoping the task exposes, not only by reading raw backing files. Use appropriate local tools for the input formats present. Do not inspect any path in `ignore_paths`, including solution/reference-answer material.
2. Apply every dimension in `eval_guide.md`. Review every grading criterion and every mechanical test. Reproduce concrete counts, IDs, dates, totals, and other deterministic values from the actual task data rather than guessing.
3. If there are no mechanical tests, set `problematic_tests` to `"[]"` and `test_quality_rationale` to `"No tests in this task."`.
4. Write only a one-element JSON array using the exact schema in `eval_guide.md` to `<OUTPUT_DIR>/verdict_NNN.json`. `problematic_rubrics` and `problematic_tests` must be JSON-encoded strings; `rubric_number` must match the rubric `number`; include `task_name`.

Ensure every expected `verdict_NNN.json` exists before continuing.

## 3. Build the report
```bash
python3 <SKILL_DIR>/dq_audit.py merge --batch-dir <OUTPUT_DIR> --output <OUTPUT_DIR>/results.jsonl --html <OUTPUT_DIR>/report.html
```

## 4. Verify flagged findings
For each row in `results.jsonl` with `num_flags > 0`:
1. Write `OUTPUT_DIR/fp/fp_input_NNN.json` containing that row plus `"line_idx": <row index>`.
2. Have a separate reviewer read `eval_guide.md` and the corresponding `fp_input_NNN.json`, then independently re-evaluate each flagged dimension from scratch against the actual task data in `task_dir`. If the evidence is ambiguous, keep the finding.
3. Write `OUTPUT_DIR/fp/fp_check_NNN.json`:
```json
{"line_idx":0,"task_name":"<name>","corrections":{"<field>":"<replacement value>"},"fp_summary":[{"dimension":"<field/dimension>","verdict":"TRUE|FALSE_POSITIVE","reason":"<brief evidence>"}]}
```
Copy `results.jsonl` to `results_v2.jsonl`. For each `fp_check_NNN.json`, overwrite only the fields named in `corrections` on the row identified by `line_idx`, then run:
```bash
python3 <SKILL_DIR>/dq_audit.py recompute --input <OUTPUT_DIR>/results_v2.jsonl
python3 <SKILL_DIR>/dq_audit.py report --input <OUTPUT_DIR>/results_v2.jsonl --output <OUTPUT_DIR>/report_v2.html
```
