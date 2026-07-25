"""RobotBench — benchmark controllers, and the agents that write them, at robot tasks.

A defined, versioned task set across robot classes, plus a comparable **scorecard** (per-task
robustness + an overall 0–100 score), optionally tagged with the agent/model that wrote the
controller. This is the eval-data flywheel: the same harness that lets an agent close the
build→test→fix loop measures how well it did. See docs/ROBOTBENCH.md for the protocol.
"""
from __future__ import annotations

BENCHMARK_VERSION = 1

# The canonical RobotBench task set: each task is a shipped template + scenario, with the
# skill it probes. A submission runs these against a controller the agent wrote (starting
# from the broken starter) and is scored on robustness under domain randomization.
TASKS = [
    {"id": "diff/stop-before-obstacle", "template": "differential-drive",
     "scenario": "stop-before-obstacle", "robot": "mobile-base",
     "skill": "reactive obstacle avoidance (LiDAR)"},
    {"id": "diff/reach-goal", "template": "differential-drive", "scenario": "reach-goal",
     "robot": "mobile-base", "skill": "pose goal-seeking (odometry)"},
    {"id": "diff/turn-around", "template": "differential-drive", "scenario": "turn-around",
     "robot": "mobile-base", "skill": "navigate around an obstacle to a goal"},
    {"id": "arm/reach-configuration", "template": "arm", "scenario": "reach-configuration",
     "robot": "manipulator", "skill": "joint-space position control"},
]


def scorecard(suite: dict, meta: dict | None = None) -> dict:
    """Turn an evals suite report into a comparable RobotBench scorecard.

    `score` is mean robustness ×100 (0–100). `meta` may tag the submission with the agent /
    model / iterations that produced the controller (for a leaderboard)."""
    results = suite.get("results", [])
    solved = sum(1 for r in results if r.get("robustness") == 1.0)
    return {
        "benchmark": f"RobotBench v{BENCHMARK_VERSION}",
        "score": round(suite.get("mean_robustness", 0.0) * 100, 1),
        "solved": solved,
        "tasks": len(results),
        "tasks_detail": sorted(results, key=lambda r: r.get("robustness", 0.0)),
        **(meta or {}),
    }
