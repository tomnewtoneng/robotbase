import subprocess
import types

from robotbase.robotbench.judge import judge, robustness_via_cli


def test_robustness_via_cli_parses_all_shapes(monkeypatch):
    def fake(stdout, rc=0):
        return lambda *a, **k: types.SimpleNamespace(stdout=stdout, stderr="", returncode=rc)

    # trials>=2 aggregated shape
    monkeypatch.setattr(subprocess, "run", fake('{"scenario":"s","trials":3,"robustness":0.667}'))
    assert robustness_via_cli("/p", "s", 3, 0) == 0.667
    # single-run shape (--trials 1): no robustness key -> fall back to `passed` (CLI exits 1 on fail)
    monkeypatch.setattr(subprocess, "run", fake('{"run_id":"r","scenario":"s","passed":true}'))
    assert robustness_via_cli("/p", "s", 1, 0) == 1.0
    monkeypatch.setattr(subprocess, "run", fake('{"scenario":"s","passed":false}', rc=1))
    assert robustness_via_cli("/p", "s", 1, 0) == 0.0


def test_judge_solved_only_when_fully_robust():
    assert judge("/proj", "reach-goal", runner=lambda *a: 1.0) == {"robustness": 1.0, "solved": True}
    assert judge("/proj", "reach-goal", runner=lambda *a: 0.667) == {"robustness": 0.667, "solved": False}
    assert judge("/proj", "reach-goal", runner=lambda *a: 0.0) == {"robustness": 0.0, "solved": False}


def test_judge_passes_trials_and_seed_to_runner():
    seen = {}
    def spy(project_dir, scenario, trials, seed):
        seen.update(project_dir=project_dir, scenario=scenario, trials=trials, seed=seed)
        return 1.0
    judge("/p", "turn-around", trials=5, seed=9, runner=spy)
    assert seen == {"project_dir": "/p", "scenario": "turn-around", "trials": 5, "seed": 9}
