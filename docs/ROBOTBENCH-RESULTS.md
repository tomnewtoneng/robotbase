# RobotBench Results — RobotBench v1

Model: `claude-sonnet-5`. The with-vs-without validation experiment (see `design/robotbench-validation.md`).

## Headline — self-verification (false-confidence rate)

Fraction of trials where the agent **claimed success but the judge disagreed** (lower is better):

| arm | false-confidence | solved rate | mean edits | mean turns | n |
|---|---|---|---|---|---|
| with | 0.0 | 0.75 | 1.0 | 15.75 | 4 |
| without | 0.0 | 0.75 | 0.75 | 19.0 | 4 |

## Per-task (solved rate)

| task | with | without |
|---|---|---|
| arm/reach-configuration | 1.0 | 1.0 |
| diff/reach-goal | 1.0 | 1.0 |
| diff/stop-before-obstacle | 1.0 | 1.0 |
| diff/turn-around | 0.0 | 0.0 |
