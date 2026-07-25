import random

from robotbase.evals import compare_suites, perturb_setup, run_trials, suite_report, trial_report
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


def test_compare_suites_flags_regressions_and_improvements():
    prev = suite_report([trial_report("a", [True, True]), trial_report("b", [True, True])])
    curr = suite_report([trial_report("a", [True, False]), trial_report("b", [True, True]),
                         trial_report("c", [True, True])])  # a regressed 1.0->0.5; c is new
    diff = compare_suites(prev, curr)
    assert diff["regressions"] == [{"scenario": "a", "from": 1.0, "to": 0.5}]
    assert diff["improvements"] == []


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
