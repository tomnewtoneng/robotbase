"""Orchestrate a scenario against a runtime and produce a structured result.

The runtime dependency is injected (duck-typed) so this module is unit-testable
with a fake and reused unchanged against the real Runtime.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

from robotbase.assertions import evaluate
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
    result.write(f"{run_dir}/{result.run_id}")
    return result
