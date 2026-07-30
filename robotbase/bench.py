"""RobotBench — benchmark controllers, and the agents that write them, at robot tasks.

A defined, versioned task set across robot classes, plus a comparable **scorecard** (per-task
robustness + an overall 0–100 score), optionally tagged with the agent/model that wrote the
controller. This is the eval-data flywheel: the same harness that lets an agent close the
build→test→fix loop measures how well it did. See docs/ROBOTBENCH.md for the protocol.
"""
from __future__ import annotations

BENCHMARK_VERSION = 2

# The canonical RobotBench v2 task set: from-scratch **authoring** tasks that probe the compiler
# + knowledge layer, not a fix-a-controller loop. The agent authors a robot+world (or imports and
# augments a URDF); a single **provided** controller (byte-identical across arms, immutable to the
# agent) must then succeed against it, scored from Gazebo ground-truth pose by the authoring judge.
# See docs/design/robotbench-suite-v2.md ("The suite") — prompts are copied verbatim from there.
TASKS = [
    {"id": "author/diff-lidar-world", "kind": "author", "robot": "mobile-base",
     "skill": "author robot+world from spec", "model_name": "robot",
     "controller": "stop_at_1m", "judge_scenario": "author_stop_at_1m",
     "prompt": "Build a differential-drive robot named `robot` with a forward-facing 2-D LiDAR, "
               "in a 6x6 m walled world containing a box obstacle at (2, 0). It must respond to "
               "/cmd_vel and publish /scan."},
    {"id": "author/sensor-on-mast", "kind": "author", "robot": "mobile-base",
     "skill": "author robot+world from spec", "model_name": "robot",
     "controller": "stop_at_1m", "judge_scenario": "author_mast_clear",
     "prompt": "Build a differential-drive robot named `robot` with a 2-D LiDAR mounted on a mast "
               "0.5 m above the chassis, in a 6x6 m walled world containing a 0.6 m-tall box at "
               "(2, 0). It must stop before the box, respond to /cmd_vel, and publish /scan."},
    {"id": "author/two-sensor", "kind": "author", "robot": "mobile-base",
     "skill": "author robot+world from spec", "model_name": "robot",
     "controller": "stop_at_1m", "judge_scenario": "author_two_sensor",
     "prompt": "Build a differential-drive robot named `robot` with both a forward LiDAR (/scan) "
               "and a forward camera (/image), in a 6x6 m walled world with a box at (2, 0). "
               "Respond to /cmd_vel."},
    {"id": "import/add-sensor", "kind": "import", "robot": "mobile-base",
     "skill": "import + augment an existing URDF", "model_name": "robot",
     "controller": "stop_at_1m", "judge_scenario": "author_stop_at_1m",
     "import_urdf": "vendor_bot.urdf",
     "prompt": "Bring the provided vendor_bot.urdf under management and add a forward LiDAR so the "
               "robot publishes /scan, in the provided world. Respond to /cmd_vel, spawn as model "
               "`robot`."},
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
