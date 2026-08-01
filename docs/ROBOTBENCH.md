# RobotBench

A standard benchmark for **robot-behavior controllers — and the AI agents that write them.**

In the LLM era, evals/benchmarks (SWE-bench, MMLU, …) became strategically enormous: they
define progress and concentrate mindshare. **Physical AI has almost no standardized
behavioral eval infrastructure.** Robotbase is uniquely positioned to fill that gap — it
already has the harness (create → author → build → test → verify), the machine-readable results,
and the sim-agnostic runner. RobotBench turns that into a scored, comparable benchmark.

> **Status.** Two layers: (1) a **controller scorecard** (`robotbase bench`, below) that scores a
> written controller against a project's scenarios; (2) the **agent benchmark** — the meta-layer that
> measures a coding agent building + verifying robots. The agent benchmark has since moved to
> *authoring* tasks (v2): the agent authors the robot **and** the world from the declarative specs,
> not just implements a controller — the broader capability the tool now targets. A full statistical
> run (n=3) is pending; results will be published here when complete, so the numbers below and in
> `ROBOTBENCH-RESULTS.md` are preliminary and held internally for now.

## The task set (v1)

Each task is a shipped template + scenario; a submission is a controller the solver wrote,
scored on **robustness under domain randomization** (not a single lucky pass).

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

1. Generate the scaffold — a bare project (v2: `robot.yaml`/`world.yaml` reset to authoring stubs;
   v1: a shipped template with a starter controller).
2. Give a coding agent only the scaffold + `AGENTS.md` + the Robotbase tools (CLI/MCP). Do
   **not** give it the solution.
3. Let it iterate: author the specs / controller → `robotbase build`/`test`/`diagnose` → repeat.
   Count the iterations.
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
