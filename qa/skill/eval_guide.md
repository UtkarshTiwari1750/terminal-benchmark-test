# Task QA Evaluation Guide

<!-- Transcribed verbatim from "Task QA Runbook v2", Appendix B. -->

Evaluate one task using its prompt, grading artifacts, tests, and the environment/resources available to the task at runtime. Verify concrete claims directly from the task data and write the JSON verdict defined below.

## Operating assumptions
- These tasks may intentionally use concise or open-ended prompts. The task can require the model to explore its inputs to determine the specific work to perform.
- Judge availability from the task's actual runtime view. Rubrics, tests, answer keys, and reference solutions are grading-side artifacts unless the task explicitly exposes them.
- Resources that are legitimately discoverable or obtainable in the task runtime count as available. Do not treat a grading artifact's presence in the task directory as evidence that the model can see it.
- A task may be graded by rubric criteria, mechanical tests, or both. Evaluate the two mechanisms together where the guide says to assess combined coverage.

## 1. Prompt clarity
`prompt_clarity` (1-5):
- 1: the objective is contradictory or cannot be determined even after examining the task data.
- 2: the instruction is so vague that there is no discernible direction.
- 3: meaningful ambiguity remains after examining the available inputs, preventing the model from determining the correct action for a substantial part of the task.
- 4: the overall intent is clear, with only minor ambiguity.
- 5: the objective and expected action are clear.

Do not lower the score merely because the prompt omits explicit file paths or does not enumerate every subtask when the required work can reasonably be inferred from the runtime data.

`is_agentic` (yes/no): whether completing the task requires multi-step exploration/tool use rather than a single-shot answer.

## 2. Grading-criterion integrity
Review every rubric criterion. For each criterion, assess all of the following:
1. **Evaluability.** A grader must be able to make a reliable pass/fail judgment. A criterion is not evaluable if it is too vague to distinguish pass from fail.
2. **Accuracy.** The criterion must agree with what the prompt and task data jointly require. It is inaccurate when it conflicts with the prompt or with the data actually available under the task's runtime scoping.
3. **Weight direction.** The sign of a weighted criterion must match its intent. A `sign_error` exists when desired behavior is assigned a negative weight or undesired behavior is assigned a positive weight. This includes desired criteria phrased as avoiding, excluding, or not doing something.

Verification rules:
- Read the actual task data before judging a criterion. Reproduce embedded counts, IDs, dates, totals, and other deterministic values from the source data.
- Verify values through the same interface, filtering, permissions, or scoping the model actually encounters. Raw backing files may contain records or ranges that are not visible through the task interface.
- A value or action implied deterministically by the task data can be a valid grading target even when the prompt does not state that value verbatim.
- Deterministic answer-key criteria are valid when the expected answer can be derived from the task data.
- Do not treat intentionally absent information as a defect when the grading criteria coherently make that absence part of the challenge, such as testing inference, hallucination resistance, or graceful handling of missing data.
- Resources legitimately discoverable at runtime count as available.
- Use `overly_specific` only when the criterion selects one arbitrary choice among multiple equally valid choices without task/data justification.
- Use `inaccurate` only for a genuine conflict with the prompt or task data, not simply because a value is not restated in the prompt.

`problematic_rubrics` issue values: `not_evaluable`, `inaccurate`, `sign_error`, `overly_specific`.

## 3. Mechanical-test correctness
If there are no mechanical tests, set `problematic_tests` to `"[]"` and `test_quality_rationale` to `"No tests in this task."`, then evaluate coverage using the rubric criteria alone.

Otherwise inspect every test function and judge the actual assertions rather than the test name or comments.
- First determine whether the same requirement is already covered by a rubric. If so, a weak test may be only a redundant safety check; flag it only when the test itself contains a substantive defect.
- Flag incorrect expected values or endpoints.
- Flag assertions that are tautological or effectively cannot fail.
- Flag change-only comparisons, such as checking that a value changed from a seed state, when a verifiable correct target exists and should be asserted instead.
- Flag matching rules, tolerances, or regular expressions that are unjustifiably strict or fragile.
- Keyword-list matching for free-form content is not inherently defective; flag it only when the allowed list is unreasonably narrow for valid responses.

`problematic_tests` `issue_type` values: `incorrect_assertion`, `wrong_endpoint`, `brittle_match`, `tautological`, `other`.

## 4. Coverage and weighting
Assess rubric criteria and mechanical tests as one combined grading pool. The scoring basis is the sum of weights for passed grading items divided by the sum of positive weights. A requirement covered by a valid test does not also need a rubric criterion, and vice versa.

`criteria_completeness` (1-5):
- 1: major required outcomes have no rubric or test coverage.
- 3: the core outcomes are covered, but meaningful gaps remain.
- 5: all important, gradable outcomes are covered with no meaningful gaps.

Do not count as uncovered a requirement that is already verified by a deterministic answer-key criterion, or an internal execution detail that no grader can reliably observe, such as hidden reasoning or exact tool-call order.

`uncovered_requirements`: comma-separated list or empty string.

`has_redundancies` (yes/no): whether rubric/test items materially grade the same requirement more than once.

`score_distribution_reasonable` (yes/no): whether the most important requirements receive the greatest weight and all weight signs match their intended behavior. If any rubric has a `sign_error`, return `no`. Do not use this field to represent factual inaccuracy in a criterion; factual errors belong under grading-criterion integrity.

## 5. Task/input adequacy
`is_self_contained` (yes/no): whether the task can be completed as defined using the provided runtime data/environment plus resources legitimately discoverable at runtime. Return `no` only when the task is genuinely unsolvable, not for a minor imperfection.

`input_adequacy` (1-5):
- 1: critical information is missing and the task cannot be completed.
- 3: most required information is available, but notable gaps remain.
- 5: all required data is available.

Before scoring input adequacy below 5, check whether the apparent absence is intentionally part of what the task is testing. Runtime-discoverable data counts as available.

`environment_adequacy` (1-5): whether the runtime tools/services are sufficient for the task. Reserve scores of 1-2 for a genuinely missing specialized capability. Do not lower environment adequacy because a valid service/query returns no matching data; that is a data/input question rather than a missing-tool problem.

`missing_data`: comma-separated list or empty string.

`missing_tools`: comma-separated list or empty string. Include only genuinely missing specialized services/capabilities, not ordinary filesystem, document, spreadsheet, PDF, CSV, or image handling that is available in the runtime.

## Required output
Write only a one-element JSON array to the assigned verdict file:
```json
[{"task_name":"<from batch>","prompt_clarity":4,"is_agentic":"yes","prompt_quality_rationale":"<brief>","problematic_rubrics":"[{\"rubric_number\":1,\"criterion\":\"...\",\"issue\":\"inaccurate\",\"rationale\":\"...\"}]","rubric_quality_rationale":"<brief>","problematic_tests":"[]","test_quality_rationale":"<brief>","criteria_completeness":4,"uncovered_requirements":"","has_redundancies":"no","score_distribution_reasonable":"yes","coverage_and_balance_rationale":"<brief>","is_self_contained":"yes","input_adequacy":5,"environment_adequacy":5,"missing_data":"","missing_tools":"","task_adequacy_rationale":"<brief>","error":""}]
```
`problematic_rubrics` and `problematic_tests` must be strings containing JSON arrays. `rubric_number` must match the rubric `number`. `task_name` is required.
