# RobotBench Results — RobotBench v1

Model: `claude-sonnet-5`. The with-vs-without validation experiment (see `design/robotbench-validation.md`).

## Headline

**solved rate** (higher better) · **capped rate** = ran out of turns without concluding (lower better; an agent that always caps couldn't tell it was done) · **self-verify acc.** = of the runs the agent *concluded on its own*, fraction where its SOLVED/NOT_SOLVED claim matched the judge (higher better; capped runs excluded so 'not finished' isn't miscounted as 'mis-verified') · **fp/fn** = false positive (claimed but didn't solve) / false negative (solved but didn't claim), among concluded runs.

| arm | solved | capped | self-verify acc. | fp | fn | mean turns | n (concluded) |
|---|---|---|---|---|---|---|---|
| with | 0.75 | 0.25 | 1.0 | 0.0 | 0.0 | 15.75 | 4 (3) |
| without | 0.75 | 1.0 | - | - | - | 19.0 | 4 (0) |

## Per-task (solved rate)

| task | with | without |
|---|---|---|
| arm/reach-configuration | 1.0 | 1.0 |
| diff/reach-goal | 1.0 | 1.0 |
| diff/stop-before-obstacle | 1.0 | 1.0 |
| diff/turn-around | 0.0 | 0.0 |
