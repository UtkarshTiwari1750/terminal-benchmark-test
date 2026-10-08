# Rollout evidence

Fill in after running five attempts against one frozen task revision:

```sh
harbor run -p ./sw-calculator -a claude-code -m <model-id> -k 5 -n 1 -o jobs/
```

Per trial, Harbor writes the agent logs and `verifier/` (`reward.txt`, `criteria.json`, `probe-output.log`). Count steps from the agent trajectory, i.e. the number of agent commands/tool calls.

| Rollout | Model | Reward | Weighted score | Energy | Forces | Stress | Hessian | Scale+MD | Steps | Where it failed |
|---|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---:|---|
| 1 | | | | | | | | | | |
| 2 | | | | | | | | | | |
| 3 | | | | | | | | | | |
| 4 | | | | | | | | | | |
| 5 | | | | | | | | | | |

Oracle: `harbor run -p ./sw-calculator -a oracle -k 5` → __/5

## Failure notes

<!-- One short paragraph per failed rollout: which criterion, which metric from criteria.json, and the root cause seen in the trajectory. -->

## Acceptance checks (author brief)

- [ ] Oracle 5/5
- [ ] ≤ 2/5 full passes on the target model (and not 0/5 on both models, otherwise flag)
- [ ] Weighted scores spread, not clustered in a narrow band
- [ ] Successful rollout ≥ 100 steps
- [ ] instruction.md ≤ 600 words (currently 435 by wc)
- [ ] QC/QA script passes
