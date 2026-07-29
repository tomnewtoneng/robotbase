"""Orchestrate one trial and a full run. Real deps shell to the CLI (generate/start_sim/judge);
fakes make the orchestration offline-testable. See docs/design/robotbench-validation.md."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from robotbase.robotbench.agent import Agent, Caps
from robotbase.robotbench.records import TrialRecord


def _slug(task_id: str) -> str:
    return task_id.replace("/", "_")


def new_run_dir(results_root: str) -> str:
    """Create and return a fresh timestamped run dir, `<results_root>/runs/<UTC>-v2/`, so every
    RobotBench run persists to its own durable, sortable location that can be interrogated later."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(results_root, "runs", f"{stamp}-v2")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def write_manifest(run_dir: str, meta: dict) -> None:
    """Record what produced this run (model, benchmark version, seeds, arms, timestamp, ...)."""
    meta = {"written_at": datetime.now(timezone.utc).isoformat(), **meta}
    with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)


def run_trial(task, arm, model, trial, seed, agent: Agent, *,
              generate, start_sim, judge_fn, caps=None, teardown_fn=None,
              transcript_dir=None) -> TrialRecord:
    project = generate(task, trial)
    try:
        start_sim(project)
        res = agent.run(project, arm, task, caps or Caps())
        verdict = judge_fn(project, task["scenario"], seed)
        transcript_path = None
        if transcript_dir is not None:
            # Persist the full agent transcript so every claim is auditable — the whole point of
            # RobotBench is evidence, not vibes, so a claimed_solved must be inspectable.
            os.makedirs(transcript_dir, exist_ok=True)
            transcript_path = os.path.join(
                transcript_dir, f"{_slug(task['id'])}-{arm}-{trial}.transcript.json")
            with open(transcript_path, "w", encoding="utf-8") as fh:
                fh.write(res.transcript)
        return TrialRecord(
            task_id=task["id"], arm=arm, model=model, trial=trial, seed=seed,
            solved=verdict["solved"], robustness=verdict["robustness"],
            claimed_solved=res.claimed_solved, controller_edits=res.controller_edits,
            agent_turns=res.agent_turns, wall_clock_s=res.wall_clock_s, tokens=res.tokens,
            stop_reason=res.stop_reason, transcript_path=transcript_path)
    finally:
        if teardown_fn is not None:
            teardown_fn(project)


def run(tasks, arms, model, trials, agent: Agent, *,
        generate, start_sim, judge_fn, seed0=0, caps=None, teardown_fn=None,
        transcript_dir=None) -> list[TrialRecord]:
    records = []
    for task in tasks:
        for arm in arms:
            for trial in range(trials):
                records.append(run_trial(task, arm, model, trial, seed0 + trial, agent,
                                         generate=generate, start_sim=start_sim,
                                         judge_fn=judge_fn, caps=caps, teardown_fn=teardown_fn,
                                         transcript_dir=transcript_dir))
    return records
