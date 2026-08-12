from robotbase.cli import _build_parser

import random

from robotbase.evals import ci_suite_report, compare_suites, perturb_setup, run_trials, suite_report, trial_report
from robotbase.schema import (
    ObstacleSpec, Pose, PoseJitter, RandomizeSpec, RobotSetup, Scenario, Size, SetupSpec,
    ActionSpec, AssertionSpec,
)
from robotbase.results import Metrics


def _setup():
    return SetupSpec(
        reset_world=True,
        robot=RobotSetup(pose=Pose(x=0.0, y=0.0, yaw=0.0)),
        obstacles=[ObstacleSpec(id="box", pose=Pose(x=2.0, y=0.0, z=0.25),
                                size=Size(x=0.5, y=1.0, z=0.5))],
    )


def test_perturb_setup_stays_within_ranges():
    rnd = RandomizeSpec(robot_pose=PoseJitter(x=0.5, y=0.5, yaw=0.2),
                        obstacles=PoseJitter(x=0.3, y=0.3))
    rng = random.Random(1)
    out = perturb_setup(_setup(), rnd, rng)
    assert abs(out.robot.pose.x) <= 0.5 and abs(out.robot.pose.y) <= 0.5
    assert abs(out.robot.pose.yaw) <= 0.2
    assert abs(out.obstacles[0].pose.x - 2.0) <= 0.3
    assert out.obstacles[0].pose.z == 0.25            # z untouched
    assert out.obstacles[0].size.x == 0.5             # size untouched


def test_perturb_setup_zero_jitter_is_identity():
    out = perturb_setup(_setup(), RandomizeSpec(), random.Random(0))
    assert out.robot.pose.x == 0.0
    assert out.obstacles[0].pose.x == 2.0


def test_trial_and_suite_reports():
    tr = trial_report("s", [True, False, True, True])
    assert tr == {"scenario": "s", "trials": 4, "passed": 3, "robustness": 0.75}
    suite = suite_report([
        trial_report("a", [True, True]),      # robustness 1.0
        trial_report("b", [True, False]),     # robustness 0.5
    ])
    assert suite["scenarios"] == 2
    assert suite["fully_passed"] == 1
    assert suite["mean_robustness"] == 0.75
    assert suite["results"][0]["scenario"] == "b"   # sorted worst-first



def test_ci_suite_report_has_machine_readable_failure_summary():
    report = ci_suite_report(suite_report([
        trial_report("passing", [True, True]),
        trial_report("flaky", [True, False]),
    ]), trials=2, seed=7)
    assert report["schema_version"] == 1
    assert report["config"] == {"trials": 2, "seed": 7}
    assert report["passed"] is False
    assert report["failed_scenarios"] == [
        {"scenario": "flaky", "trials": 2, "passed": 1, "robustness": 0.5}]

def test_compare_suites_flags_regressions_and_improvements():
    prev = suite_report([trial_report("a", [True, True]), trial_report("b", [True, True])])
    curr = suite_report([trial_report("a", [True, False]), trial_report("b", [True, True]),
                         trial_report("c", [True, True])])  # a regressed 1.0->0.5; c is new
    diff = compare_suites(prev, curr)
    assert diff["regressions"] == [{"scenario": "a", "from": 1.0, "to": 0.5}]
    assert diff["improvements"] == []


def test_run_eval_stops_between_trials(tmp_path):
    import threading
    import pytest
    from robotbase.evals import run_eval
    from robotbase.scenario_runner import RunStopped

    stop = threading.Event()
    calls = {"n": 0}

    class StoppingRuntime(_FakeRuntime):
        def run_action(self, action):
            calls["n"] += 1
            stop.set()          # cancel after the first trial's action runs

    scenario = Scenario(
        version=1, name="drive", setup=_setup(),
        actions=[ActionSpec(type="wait", duration_seconds=0.01)],
        assertions=[AssertionSpec(type="robot_moved_minimum_distance", minimum_distance_metres=1.0)],
        randomize=RandomizeSpec(robot_pose=PoseJitter(x=0.2)),
    )
    with pytest.raises(RunStopped):
        run_eval(scenario, StoppingRuntime(Metrics(distance_travelled_metres=2.0)),
                 str(tmp_path), trials=5, seed=0, stop_event=stop)
    assert calls["n"] <= 2      # stopped early, not all 5 trials


class _FakeRuntime:
    def __init__(self, metrics):
        self._m = metrics
    def reset(self): pass
    def set_robot_pose(self, pose): pass
    def spawn_box(self, obs): pass
    def run_action(self, action): pass
    def collect_metrics(self): return self._m


def test_run_trials_reports_robustness(tmp_path):
    scenario = Scenario(
        version=1, name="drive",
        actions=[ActionSpec(type="wait", duration_seconds=1)],
        assertions=[AssertionSpec(type="robot_moved_minimum_distance", minimum_distance_metres=1.0)],
        randomize=RandomizeSpec(robot_pose=PoseJitter(x=0.2)),
    )
    passing = Metrics(distance_travelled_metres=2.0)
    report = run_trials(scenario, _FakeRuntime(passing), str(tmp_path), trials=3, seed=0)
    assert report == {"scenario": "drive", "trials": 3, "passed": 3, "robustness": 1.0}


from robotbase.evals import run_eval, run_eval_suite


def test_run_eval_randomized_reports_ci_and_per_trial(tmp_path):
    scenario = Scenario(
        version=1, name="drive",
        actions=[ActionSpec(type="wait", duration_seconds=1)],
        assertions=[AssertionSpec(type="robot_moved_minimum_distance", minimum_distance_metres=1.0)],
        randomize=RandomizeSpec(robot_pose=PoseJitter(x=0.2)),
    )
    report = run_eval(scenario, _FakeRuntime(Metrics(distance_travelled_metres=2.0)),
                      str(tmp_path), trials=5, seed=0)
    assert report["eval_id"].startswith("eval_")
    assert report["config"] == {"scenario": "drive", "trials": 5, "seed": 0}
    assert report["n"] == 5 and report["passed"] == 5 and report["success_rate"] == 1.0
    assert report["randomized"] is True and report["ci95"] is not None
    assert len(report["per_trial"]) == 5
    assert all("run_id" in t and "seed" in t for t in report["per_trial"])
    # deterministic per base seed: same seed -> same per-trial seeds
    again = run_eval(scenario, _FakeRuntime(Metrics(distance_travelled_metres=2.0)),
                     str(tmp_path), trials=5, seed=0)
    assert [t["seed"] for t in report["per_trial"]] == [t["seed"] for t in again["per_trial"]]


def test_run_eval_deterministic_marks_no_ci(tmp_path):
    scenario = Scenario(
        version=1, name="hold",
        actions=[ActionSpec(type="wait", duration_seconds=1)],
        assertions=[AssertionSpec(type="robot_moved_minimum_distance", minimum_distance_metres=1.0)],
        randomize=RandomizeSpec(),   # no jitter
    )
    report = run_eval(scenario, _FakeRuntime(Metrics(distance_travelled_metres=2.0)),
                      str(tmp_path), trials=3, seed=0)
    assert report["deterministic"] is True and report["ci95"] is None
    assert report["n"] == 3 and report["success_rate"] == 1.0




def test_eval_cli_accepts_json_output():
    args = _build_parser().parse_args(["eval", "drive-forward", "--json"])
    assert args.cmd == "eval" and args.scenario == "drive-forward" and args.json is True

def test_run_eval_reports_each_completed_trial(tmp_path):
    scenario = Scenario(
        version=1, name="progress",
        actions=[ActionSpec(type="wait", duration_seconds=1)],
        assertions=[AssertionSpec(type="robot_moved_minimum_distance", minimum_distance_metres=1.0)],
        randomize=RandomizeSpec(robot_pose=PoseJitter(x=0.2)),
    )
    events = []
    run_eval(scenario, _FakeRuntime(Metrics(distance_travelled_metres=2.0)), str(tmp_path),
             trials=2, seed=0, progress=events.append)
    assert [(event["trial"], event["trials"], event["passed"]) for event in events] == [
        (1, 2, True), (2, 2, True)]
    assert all(event["scenario"] == "progress" and event["run_id"] for event in events)

def test_run_eval_suite_aggregates(tmp_path):
    s1 = Scenario(version=1, name="a",
                  actions=[ActionSpec(type="wait", duration_seconds=1)],
                  assertions=[AssertionSpec(type="robot_moved_minimum_distance", minimum_distance_metres=1.0)],
                  randomize=RandomizeSpec(robot_pose=PoseJitter(x=0.2)))
    report = run_eval_suite([s1], _FakeRuntime(Metrics(distance_travelled_metres=2.0)),
                            str(tmp_path), trials=2, seed=0)
    assert report["eval_id"].startswith("eval_")
    assert report["scenarios"] == 1 and report["results"][0]["scenario"] == "a"
