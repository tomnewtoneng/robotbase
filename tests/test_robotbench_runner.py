from robotbase.robotbench.runner import run_trial, run
from robotbase.robotbench.agent import StubAgent, AgentResult
from robotbase.robotbench.records import TrialRecord, false_confidence

TASK = {"id": "diff/reach-goal", "template": "differential-drive", "scenario": "reach-goal",
        "robot": "mobile-base", "skill": "pose goal-seeking"}


def _deps(robustness):
    return dict(generate=lambda task, trial: f"/tmp/{task['scenario']}-{trial}",
                start_sim=lambda project: None,
                judge_fn=lambda project, scenario, seed: {"robustness": robustness,
                                                          "solved": robustness == 1.0})


def test_run_trial_builds_a_record_from_agent_and_judge():
    agent = StubAgent(solution="x", claim=True, edits=5, turns=8)
    # replace run so it doesn't touch a real fs
    agent.run = lambda project, arm, task, caps: AgentResult(
        claimed_solved=True, controller_edits=5, agent_turns=8, wall_clock_s=3.0,
        tokens=None, stop_reason="declared_done", transcript="t")
    rec = run_trial(TASK, "without", "claude-sonnet-5", 0, 7, agent, **_deps(0.5))
    assert isinstance(rec, TrialRecord)
    assert rec.arm == "without" and rec.solved is False and rec.robustness == 0.5
    assert rec.claimed_solved is True and rec.controller_edits == 5 and rec.seed == 7
    assert false_confidence(rec) is True                     # claimed but unsolved


def test_run_iterates_tasks_arms_trials():
    agent = StubAgent(solution="x", claim=False, edits=1, turns=1)
    agent.run = lambda project, arm, task, caps: AgentResult(
        False, 1, 1, 1.0, None, "declared_done", "t")
    recs = run([TASK], ["with", "without"], "m", 3, agent, **_deps(1.0))
    assert len(recs) == 6                                     # 1 task x 2 arms x 3 trials
    assert {r.arm for r in recs} == {"with", "without"}
    assert sorted(r.seed for r in recs if r.arm == "with") == [0, 1, 2]
