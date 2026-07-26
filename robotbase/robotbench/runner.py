"""Orchestrate one trial and a full run. Real deps shell to the CLI (generate/start_sim/judge);
fakes make the orchestration offline-testable. See docs/design/robotbench-validation.md."""
from __future__ import annotations

from robotbase.robotbench.agent import Agent, Caps
from robotbase.robotbench.records import TrialRecord


def run_trial(task, arm, model, trial, seed, agent: Agent, *,
              generate, start_sim, judge_fn, caps=None, teardown_fn=None) -> TrialRecord:
    project = generate(task, trial)
    try:
        start_sim(project)
        res = agent.run(project, arm, task, caps or Caps())
        verdict = judge_fn(project, task["scenario"], seed)
        return TrialRecord(
            task_id=task["id"], arm=arm, model=model, trial=trial, seed=seed,
            solved=verdict["solved"], robustness=verdict["robustness"],
            claimed_solved=res.claimed_solved, controller_edits=res.controller_edits,
            agent_turns=res.agent_turns, wall_clock_s=res.wall_clock_s, tokens=res.tokens,
            stop_reason=res.stop_reason)
    finally:
        if teardown_fn is not None:
            teardown_fn(project)


def run(tasks, arms, model, trials, agent: Agent, *,
        generate, start_sim, judge_fn, seed0=0, caps=None, teardown_fn=None) -> list[TrialRecord]:
    records = []
    for task in tasks:
        for arm in arms:
            for trial in range(trials):
                records.append(run_trial(task, arm, model, trial, seed0 + trial, agent,
                                         generate=generate, start_sim=start_sim,
                                         judge_fn=judge_fn, caps=caps, teardown_fn=teardown_fn))
    return records
