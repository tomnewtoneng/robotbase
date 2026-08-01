# RobotBench Results — RobotBench v2

> **⚠️ PRELIMINARY — n=1 (one trial per task). Directional, not statistical.** These numbers are
> **held back from public / marketing materials until a full n=3 run** — don't cite them externally
> yet (README and docs say "benchmark data coming soon"). This file is the internal record of the
> first clean run; the seeded-spawn robustness (fixed 2026-08-01) makes a proper n=3 meaningful.

Model: `claude-sonnet-5`. The with-vs-without validation experiment (see `design/robotbench-validation.md`).

## Headline

**solved rate** (higher better) · **capped rate** = ran out of turns without concluding (lower better; an agent that always caps couldn't tell it was done) · **self-verify acc.** = of the runs the agent *concluded on its own*, fraction where its SOLVED/NOT_SOLVED claim matched the judge (higher better; capped runs excluded so 'not finished' isn't miscounted as 'mis-verified') · **fp/fn** = false positive (claimed but didn't solve) / false negative (solved but didn't claim), among concluded runs.

| arm | solved | capped | self-verify acc. | fp | fn | mean turns | n (concluded) |
|---|---|---|---|---|---|---|---|
| with | 0.75 | 0.0 | 0.75 | 0.25 | 0.0 | 33.25 | 4 (4) |
| without | 0.0 | 0.5 | 0.0 | 1.0 | 0.0 | 40.25 | 4 (2) |

## Per-task (solved rate)

| task | with | without |
|---|---|---|
| author/diff-lidar-world | 1.0 | 0.0 |
| author/sensor-on-mast | 1.0 | 0.0 |
| author/two-sensor | 1.0 | 0.0 |
| import/add-sensor | 0.0 | 0.0 |
