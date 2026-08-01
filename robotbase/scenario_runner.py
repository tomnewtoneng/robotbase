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
from robotbase.recording import embed_attachment, episode_sidecar
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

    # Enforce the whole-scenario budget: stop before any action once the deadline passes, so a
    # scenario whose actions overrun `timeout_seconds` is cut off and fails instead of running
    # unbounded. (A single blocking runtime call isn't interrupted here — that is the runtime's
    # responsibility — but multi-action / long-scenario overruns are bounded at action granularity.)
    deadline = time.monotonic() + scenario.timeout_seconds
    timed_out = False
    for action in scenario.actions:
        if time.monotonic() >= deadline:
            timed_out = True
            break
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
        timed_out=timed_out,
        started_at=started_at,
        finished_at=finished_at,
    )
    run_path = f"{run_dir}/{result.run_id}"
    result.write(run_path)

    # Finalize the recorded MCAP episode and write the self-describing sidecar next to
    # the result, so the run dir is a portable, interpretable record of the episode.
    episode = runtime.finalize_episode(run_path) if hasattr(runtime, "finalize_episode") else None
    sidecar = episode_sidecar(scenario, result, episode)
    sidecar_json = json.dumps(sidecar, indent=2)
    with open(os.path.join(run_path, "episode.json"), "w") as f:
        f.write(sidecar_json)
    # Also embed the sidecar inside the .mcap so the single file is self-describing.
    if episode and episode.get("mcap"):
        embed_attachment(os.path.join(run_path, episode["mcap"]), "episode.json",
                         sidecar_json.encode())
    return result
