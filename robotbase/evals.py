"""Evals — turn scenarios (pass/fail tests) into benchmarks.

Two ideas, both sim-agnostic (they drive any SimAdapter through `run_scenario`):
- **Domain randomization:** run a scenario across N randomized configs and report a
  *robustness* fraction, not a single pass — so a controller that only works for one exact
  obstacle placement doesn't look solved.
- **Suites:** run every scenario and aggregate into one report — "CI for robot behaviors."

The perturbation and aggregation logic is pure and unit-tested; the orchestration is a thin
loop over the existing `run_scenario`.
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from robotbase.schema import ObstacleSpec, Pose, RandomizeSpec, RobotSetup, Scenario, SetupSpec


def _jit(value: float, rng: random.Random, spread: float) -> float:
    return value + rng.uniform(-spread, spread) if spread else value


def perturb_setup(setup: SetupSpec, randomize: RandomizeSpec, rng: random.Random) -> SetupSpec:
    """Return a copy of *setup* with the robot start pose and obstacle poses jittered within
    the ranges in *randomize*. Deterministic given *rng*."""
    jp = randomize.robot_pose
    pose = setup.robot.pose
    robot = RobotSetup(pose=Pose(
        x=_jit(pose.x, rng, jp.x), y=_jit(pose.y, rng, jp.y),
        z=pose.z, yaw=_jit(pose.yaw, rng, jp.yaw),
    ))
    jo = randomize.obstacles
    obstacles = [
        ObstacleSpec(
            id=o.id, type=o.type, size=o.size,
            pose=Pose(x=_jit(o.pose.x, rng, jo.x), y=_jit(o.pose.y, rng, jo.y),
                      z=o.pose.z, yaw=o.pose.yaw),
        )
        for o in setup.obstacles
    ]
    return SetupSpec(reset_world=setup.reset_world, robot=robot, obstacles=obstacles)


def trial_report(name: str, passed_flags: list[bool]) -> dict:
    """Aggregate per-trial pass/fail into a robustness report for one scenario."""
    n = len(passed_flags)
    passed = sum(1 for p in passed_flags if p)
    return {
        "scenario": name,
        "trials": n,
        "passed": passed,
        "robustness": round(passed / n, 3) if n else 0.0,
    }


def suite_report(trial_reports: list[dict]) -> dict:
    """Aggregate per-scenario trial reports into a whole-suite report."""
    total = len(trial_reports)
    fully = sum(1 for r in trial_reports if r["robustness"] == 1.0)
    mean = round(sum(r["robustness"] for r in trial_reports) / total, 3) if total else 0.0
    return {
        "scenarios": total,
        "fully_passed": fully,
        "mean_robustness": mean,
        "results": sorted(trial_reports, key=lambda r: r["robustness"]),
    }


def compare_suites(previous: dict, current: dict) -> dict:
    """Diff two suite reports by per-scenario robustness — the behavioral-regression check."""
    prev = {r["scenario"]: r["robustness"] for r in previous.get("results", [])}
    regressions, improvements = [], []
    for r in current.get("results", []):
        old = prev.get(r["scenario"])
        if old is None:
            continue
        if r["robustness"] < old:
            regressions.append({"scenario": r["scenario"], "from": old, "to": r["robustness"]})
        elif r["robustness"] > old:
            improvements.append({"scenario": r["scenario"], "from": old, "to": r["robustness"]})
    return {"regressions": regressions, "improvements": improvements}


def run_trials(scenario: Scenario, runtime: Any, run_dir: str,
               trials: int = 1, seed: int = 0) -> dict:
    """Run *scenario* *trials* times — trial 0 is the nominal (unperturbed) setup, the rest
    sample within `scenario.randomize` — and report robustness. Uses the shared run_scenario,
    so it works against any backend."""
    from robotbase.scenario_runner import run_scenario

    rng = random.Random(seed)
    flags: list[bool] = []
    for i in range(max(1, trials)):
        if i == 0:
            trial = scenario
        else:
            trial = scenario.model_copy(
                update={"setup": perturb_setup(scenario.setup, scenario.randomize, rng)})
        flags.append(run_scenario(trial, runtime, run_dir).passed)
    return trial_report(scenario.name, flags)


def run_suite(scenarios: list[Scenario], runtime: Any, run_dir: str,
              trials: int = 1, seed: int = 0) -> dict:
    """Run every scenario (each with `trials` randomized trials) and aggregate."""
    reports = [run_trials(s, runtime, run_dir, trials, seed) for s in scenarios]
    return suite_report(reports)


def run_eval(scenario: Scenario, runtime: Any, run_dir: str,
             trials: int = 10, seed: int = 0) -> dict:
    """Statistically evaluate *scenario* over *trials* randomized trials. Every trial is a sample
    (unlike run_trials, no nominal trial 0), each with a deterministic per-trial seed derived from
    *seed*. Captures the full ScenarioResult per trial and returns the persisted-report dict."""
    from robotbase.eval_stats import eval_report, is_randomized
    from robotbase.results import new_eval_id
    from robotbase.scenario_runner import run_scenario

    randomized = is_randomized(scenario.randomize)
    base = random.Random(seed)
    per_trial: list[dict] = []
    for i in range(max(1, trials)):
        tseed = base.randrange(2 ** 32)
        trial = scenario.model_copy(update={
            "setup": perturb_setup(scenario.setup, scenario.randomize, random.Random(tseed))})
        result = run_scenario(trial, runtime, run_dir)
        fields = set(result.metrics.model_fields_set)
        metrics = result.metrics.model_dump(include=fields) if fields else result.metrics.model_dump()
        per_trial.append({"index": i, "seed": tseed, "run_id": result.run_id,
                          "passed": result.passed, "metrics": metrics})
    return {
        "eval_id": new_eval_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {"scenario": scenario.name, "trials": max(1, trials), "seed": seed},
        **eval_report(scenario.name, per_trial, randomized),
    }


def run_eval_suite(scenarios: list[Scenario], runtime: Any, run_dir: str,
                   trials: int = 10, seed: int = 0) -> dict:
    """Statistically evaluate every scenario and aggregate into one suite report."""
    from robotbase.eval_stats import suite_eval_report
    from robotbase.results import new_eval_id

    reports = [run_eval(s, runtime, run_dir, trials, seed) for s in scenarios]
    return {
        "eval_id": new_eval_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": {"all": True, "trials": max(1, trials), "seed": seed},
        **suite_eval_report(reports),
    }
