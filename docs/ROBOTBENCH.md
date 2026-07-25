# RobotBench

A standard benchmark for **robot-behavior controllers — and the AI agents that write them.**

In the LLM era, evals/benchmarks (SWE-bench, MMLU, …) became strategically enormous: they
define progress and concentrate mindshare. **Physical AI has almost no standardized
behavioral eval infrastructure.** Robotbase is uniquely positioned to fill that gap — it
already has the harness (create → build → test → fix), the machine-readable results, and the
sim-agnostic runner. RobotBench turns that into a scored, comparable benchmark.

## The task set (v1)

Each task is a shipped template + scenario, starting from the deliberately-broken starter
controller. A submission is a controller the solver wrote; it's scored on **robustness under
domain randomization** (not a single lucky pass).

| Task id | Robot | Skill it probes |
|---|---|---|
| `diff/stop-before-obstacle` | mobile base | reactive obstacle avoidance (LiDAR) |
| `diff/reach-goal` | mobile base | pose goal-seeking (odometry) |
| `diff/turn-around` | mobile base | navigate around an obstacle to a goal |
| `arm/reach-configuration` | manipulator | joint-space position control |

`robotbase bench --list` prints the canonical set. The set is versioned (`RobotBench v1`);
it grows across robot classes as templates are added — the same source of un-cloneable eval
value described in `VISION.md`.

## Scoring

Robustness per task = fraction of randomized trials passed. The **scorecard** aggregates:

```json
{
  "benchmark": "RobotBench v1",
  "score": 83.3,          // mean robustness × 100 (0–100)
  "solved": 3,            // tasks at robustness 1.0
  "tasks": 4,
  "tasks_detail": [ { "scenario": "...", "trials": 3, "passed": 2, "robustness": 0.667 }, ... ],
  "agent": "claude-opus-4-8"   // optional: who wrote the controller
}
```

Run it: `robotbase bench [--trials N] [--agent NAME]` scores the current project's controller
against its scenarios. (v1 scores one robot class per project; a full cross-class run scores
each template's project and combines — the scorecard format supports it.)

## Benchmarking an *agent* (the meta-layer)

The harness that lets an agent close the loop *is* the eval. The protocol:

1. Generate the project (`robotbase create --template …`) — it ships the broken starter.
2. Give a coding agent only the project + `AGENTS.md` + the Robotbase tools (CLI/MCP). Do
   **not** give it the solution.
3. Let it iterate: `robotbase test`/`diagnose` → edit the controller → repeat. Count the
   edit→test iterations.
4. Score with `robotbase bench --agent <model>` and record the scorecard.

This is exactly the dogfooding loop already run against Claude (see `PROOF.md` and the
session history) — RobotBench formalizes it into a repeatable, comparable measurement.
Scorecards are the leaderboard unit: *which agent/model is best at writing robot
controllers, and how many iterations does it take?*

## Why this compounds

- **Un-cloneable data.** Every submission accumulates behavioral eval data a competitor
  can't get by copying the CLI (VISION's moat).
- **Mindshare.** "SWE-bench for robotics agents" is a sharp, ownable, timely story.
- **Flywheel.** The benchmark drives adoption of the scenario format (Track C — own the
  standard), which feeds the hub and the eval/data layers.
