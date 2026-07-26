from robotbase.robotbench.judge import judge


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
