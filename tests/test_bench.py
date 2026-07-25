from robotbase.bench import BENCHMARK_VERSION, TASKS, scorecard
from robotbase.evals import suite_report, trial_report


def test_tasks_are_well_formed_and_unique():
    assert TASKS
    for t in TASKS:
        assert {"id", "template", "scenario", "robot", "skill"} <= set(t)
    ids = [t["id"] for t in TASKS]
    assert len(ids) == len(set(ids))


def test_scorecard_from_suite():
    suite = suite_report([
        trial_report("a", [True, True, True]),     # robustness 1.0
        trial_report("b", [True, False, True]),    # robustness 0.667
    ])
    card = scorecard(suite, {"agent": "claude-opus-4-8"})
    assert card["benchmark"] == f"RobotBench v{BENCHMARK_VERSION}"
    assert card["tasks"] == 2
    assert card["solved"] == 1                      # only "a" is fully robust
    assert card["score"] == round(suite["mean_robustness"] * 100, 1)
    assert card["agent"] == "claude-opus-4-8"
    assert card["tasks_detail"][0]["scenario"] == "b"   # worst-first


def test_scorecard_without_meta():
    card = scorecard(suite_report([trial_report("a", [True])]))
    assert card["score"] == 100.0 and card["solved"] == 1 and "agent" not in card
