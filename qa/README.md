# Task QA (Runbook v2) for this repository

`skill/` contains the five files from the *Task QA Runbook v2* appendices, transcribed into runnable form:

- `SKILL.md` (Appendix A)
- `eval_guide.md` (Appendix B)
- `POST_ROLLOUT_SKILL.md` (Appendix C)
- `dq_audit.py` (Appendix D)
- `dq_post.py` (Appendix E)

Only line breaks and indentation lost in the PDF were restored, and the *Configuration* block was filled in for this repo. Every rule, schema and line of logic is unchanged. Both scripts were checked with sample data: `merge`, `recompute`, `report`, `stats`.

Two files are additions needed to connect these tasks to the runbook:

- `rubrics/<task>.json`: the five graded criteria per task as `{number, points, criterion}`. These are taken from the numbered "What is verified" list in each `instruction.md` and match `WEIGHTS` in `tests/grade.py`. The graders score criteria in `grade.py` rather than as pytest `def test_` functions, so the runbook needs this rubric to see the weights.
- `harbor_to_rollouts.py`: converts Harbor job folders into the rollout JSONL schema that `dq_post.py` requires, and counts agent steps. It skips trials that crashed before grading, because those are not model failures.

## 1. Install (once)

```sh
bash qa/install_skill.sh          # from the repo root
```

This copies the files to `~/.claude/skills/task-quality-qa`, fills in the absolute paths, and registers `task-quality-postrun` as a skill too. Then start a **new** Claude Code session in the repo root.

## 2. Pre-rollout QA (run before the model rollouts)

In Claude Code:

```
run task-quality-preflight on <absolute path of this repo>
```

Outputs go to `qa-output/preflight/`. Open `report.html`. For any flagged task, the skill's step 4 runs an independent second review, and the final result is `report_v2.html`. Fix only findings that the second review confirms, then rerun.

## 3. Post-rollout QA (after the model rollouts)

```sh
python3 qa/harbor_to_rollouts.py --tasks-root . --out qa-output/rollouts.jsonl --markdown \
    sw-calculator/jobs/<job-timestamp> shallow-water-wetdry/jobs/<job-timestamp>
```

Then in Claude Code:

```
run task-quality-postrun on <absolute path>/qa-output/rollouts.jsonl
```

Open `qa-output/postrun/post_report.html`. Any criterion that every rollout failed gets a root-cause verdict. Copy the `--markdown` table into each task's `evidence/rollouts.md`.

`reward` in the JSONL is the weighted criterion score by default. Harbor's own reward is binary (1 only if all five criteria pass), and it is kept as `binary_reward`. Pass `--reward binary` to use it instead. The runbook recommends at least two distinct models, so run both Opus 5 and GPT-5.6 if possible.
