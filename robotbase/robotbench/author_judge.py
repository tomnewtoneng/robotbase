"""The RobotBench v2 behavioral judge.

Given an authored project (either arm) and a task, bring the sim up at N seeded spawn poses, run
the **provided** controller against it, and score each run from the robot's Gazebo ground-truth
pose trace via the task's acceptance predicate. Robustness is the fraction of seeds that pass;
`solved` requires all of them.

Every collaborator that touches Docker/ROS is injected (`bringup_fn`, `run_controller_fn`,
`sample_fn`, `liveness_fn`), so the orchestration — the loop, the interface gate, the always-run
teardown, evidence writing, aggregation — is fully unit-testable with fakes. `cli_deps` supplies
the real implementations.
"""
from __future__ import annotations

import json
import os

from robotbase.robotbench.acceptance import SPECS, spawn_pose


def author_judge(project_dir: str, task: dict, *, bringup_fn, run_controller_fn, sample_fn,
                 liveness_fn, evidence_dir: str | None = None, trials: int = 3, seed: int = 0,
                 liveness_timeout: float = 30.0) -> dict:
    spec = SPECS[task["judge_scenario"]]
    passes = 0
    for i in range(trials):
        s = seed + i
        pose = spawn_pose(spec, s)
        ok, trace, reason = False, [], ""
        teardown = bringup_fn(project_dir, pose)
        try:
            if not liveness_fn(spec.requires, liveness_timeout):
                reason = f"required interfaces not live: {spec.requires}"
            else:
                run_controller_fn(project_dir, spec.duration_s)
                trace = sample_fn(task["model_name"], spec.duration_s)
                ok = bool(spec.predicate(trace, spec.world_obstacles))
                reason = "pass" if ok else "predicate failed"
        except Exception as e:  # a crash in bring-up/controller/sampling is a failed trial, not a crash
            reason = f"error: {e}"
        finally:
            try:
                teardown()
            except Exception:
                pass
        if ok:
            passes += 1
        if evidence_dir:
            _write_evidence(evidence_dir, s, pose, trace, ok, reason)

    robustness = passes / trials if trials else 0.0
    return {"robustness": robustness, "solved": robustness == 1.0}


def _write_evidence(evidence_dir, seed, pose, trace, ok, reason) -> None:
    d = os.path.join(evidence_dir, f"seed-{seed}")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "trace.json"), "w", encoding="utf-8") as f:
        json.dump({"pose": pose, "trace": trace}, f)
    with open(os.path.join(d, "verdict.json"), "w", encoding="utf-8") as f:
        json.dump({"seed": seed, "pose": pose, "passed": ok, "reason": reason,
                   "samples": len(trace)}, f)
