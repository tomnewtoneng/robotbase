from robotbase.schema import Scenario, SetupSpec, ActionSpec, AssertionSpec
from robotbase.results import Metrics
from robotbase.scenario_runner import run_scenario


class FakeRuntime:
    def __init__(self, metrics):
        self._m = metrics
        self.calls = []

    def reset(self):
        self.calls.append("reset")

    def set_robot_pose(self, pose):
        self.calls.append("pose")

    def spawn_box(self, obs):
        self.calls.append(f"spawn:{obs.id}")

    def run_action(self, action):
        self.calls.append(f"action:{action.type}")

    def collect_metrics(self):
        return self._m


def _scenario():
    return Scenario(
        version=1,
        name="stop-before-obstacle",
        setup=SetupSpec(reset_world=True),
        actions=[ActionSpec(type="wait", duration_seconds=1)],
        assertions=[
            AssertionSpec(type="no_collision"),
            AssertionSpec(type="minimum_obstacle_distance", minimum_metres=0.25),
        ],
    )


def test_runner_passes_when_metrics_clear(tmp_path):
    m = Metrics(
        collision_count=0,
        minimum_obstacle_distance_metres=0.4,
        distance_travelled_metres=2.0,
        final_linear_velocity=0.0,
        final_angular_velocity=0.0,
        topic_message_counts={"/scan": 20},
    )
    result = run_scenario(_scenario(), FakeRuntime(m), str(tmp_path))
    assert result.passed is True
    assert len(result.assertions) == 2


def test_runner_fails_on_collision(tmp_path):
    m = Metrics(
        collision_count=1,
        minimum_obstacle_distance_metres=0.0,
        distance_travelled_metres=2.1,
        final_linear_velocity=0.0,
        final_angular_velocity=0.0,
        topic_message_counts={"/scan": 20},
    )
    result = run_scenario(_scenario(), FakeRuntime(m), str(tmp_path))
    assert result.passed is False
    assert result.metrics.collision_count == 1
