import pathlib

from robotbase.robotbench.author_judge import author_judge

TASK = {"id": "author/diff-lidar-world", "judge_scenario": "author_stop_at_1m",
        "model_name": "robot"}


def _fakes(trace, live=True):
    calls = {"up": 0, "down": 0}

    def bringup(project, pose):
        calls["up"] += 1
        return lambda: calls.__setitem__("down", calls["down"] + 1)

    return calls, bringup, (lambda p, d: None), (lambda m, d, hz=10: trace), (lambda need, t: live)


def test_solved_when_all_trials_pass(tmp_path):
    good = [(i * 0.1, x, 0.0) for i, x in enumerate([0, 0.4, 0.8, 1.0, 1.05, 1.05])]
    calls, bringup, runc, sample, live = _fakes(good)
    out = author_judge("/p", TASK, bringup_fn=bringup, run_controller_fn=runc,
                       sample_fn=sample, liveness_fn=live, trials=3,
                       evidence_dir=str(tmp_path))
    assert out == {"robustness": 1.0, "solved": True}
    assert calls["up"] == 3 and calls["down"] == 3                 # torn down every trial
    assert len(list(pathlib.Path(tmp_path).glob("seed-*/verdict.json"))) == 3


def test_missing_interface_fails_trial_without_running():
    _, bringup, runc, sample, _ = _fakes([(0, 0, 0)])
    out = author_judge("/p", TASK, bringup_fn=bringup, run_controller_fn=runc,
                       sample_fn=sample, liveness_fn=(lambda need, t: False), trials=2)
    assert out["solved"] is False and out["robustness"] == 0.0


def test_teardown_runs_even_if_controller_raises():
    calls, bringup, _, sample, live = _fakes([(0, 0, 0)])

    def boom(p, d):
        raise RuntimeError("controller crashed")

    out = author_judge("/p", TASK, bringup_fn=bringup, run_controller_fn=boom,
                       sample_fn=sample, liveness_fn=live, trials=1)
    assert out["solved"] is False and calls["down"] == 1
