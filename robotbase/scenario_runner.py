"""Orchestrate a scenario against a runtime and produce a structured result.

The runtime dependency is injected (duck-typed) so this module is unit-testable
with a fake and reused unchanged against the real Runtime.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

from robotbase.assertions import evaluate
from robotbase.recording import episode_sidecar
from robotbase.results import ScenarioResult, new_run_id
from robotbase.schema import Scenario


def run_scenario(scenario: Scenario, runtime, run_dir: str) -> ScenarioResult:
    started = time.time()
    started_at = datetime.now(timezone.utc).isoformat()

    if scenario.setup.reset_world:
        runtime.reset()
    runtime.set_robot_pose(scenario.setup.robot.pose)
    for obstacle in scenario.setup.obstacles:
        runtime.spawn_box(obstacle)

    for action in scenario.actions:
        runtime.run_action(action)

    metrics = runtime.collect_metrics()
    assertion_results = [evaluate(a, metrics) for a in scenario.assertions]
    finished_at = datetime.now(timezone.utc).isoformat()

    result = ScenarioResult(
        run_id=new_run_id(),
        scenario=scenario.name,
        metrics=metrics,
        assertions=assertion_results,
        duration_seconds=round(time.time() - started, 1),
        started_at=started_at,
        finished_at=finished_at,
    )
    run_path = f"{run_dir}/{result.run_id}"
    result.write(run_path)

    # Finalize the recorded MCAP episode and write the self-describing sidecar next to
    # the result, so the run dir is a portable, interpretable record of the episode.
    episode = runtime.finalize_episode(run_path) if hasattr(runtime, "finalize_episode") else None
    with open(os.path.join(run_path, "episode.json"), "w") as f:
        json.dump(episode_sidecar(scenario, result, episode), f, indent=2)
    return result
