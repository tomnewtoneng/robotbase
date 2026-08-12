import threading
import time

import pytest

from robotbase.schema import Scenario, SetupSpec, ActionSpec, AssertionSpec
from robotbase.results import Metrics
from robotbase.scenario_runner import RunStopped, interruptible_sleep, run_scenario


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


class SlowRuntime(FakeRuntime):
    def run_action(self, action):
        super().run_action(action)
        time.sleep(0.03)


def test_runner_enforces_scenario_timeout(tmp_path):
    # a scenario whose actions overrun timeout_seconds is cut off and fails (not silently over-run)
    m = Metrics(collision_count=0, minimum_obstacle_distance_metres=0.4,
                topic_message_counts={"/scan": 20})
    scenario = Scenario(
        version=1, name="slow", setup=SetupSpec(reset_world=True), timeout_seconds=0.05,
        actions=[ActionSpec(type="wait", duration_seconds=1),
                 ActionSpec(type="wait", duration_seconds=1),
                 ActionSpec(type="wait", duration_seconds=1)],
        assertions=[AssertionSpec(type="no_collision")])
    rt = SlowRuntime(m)
    result = run_scenario(scenario, rt, str(tmp_path))
    assert result.timed_out is True
    assert result.passed is False                                   # a timeout fails the scenario
    assert len([c for c in rt.calls if c.startswith("action:")]) < 3  # stopped early


def test_interruptible_sleep_wakes_on_stop():
    stop = threading.Event()
    threading.Timer(0.05, stop.set).start()
    start = time.monotonic()
    with pytest.raises(RunStopped):
        interruptible_sleep(5.0, stop)
    assert time.monotonic() - start < 1.0   # woke early, didn't sleep the full 5s


def test_interruptible_sleep_without_event_completes():
    start = time.monotonic()
    interruptible_sleep(0.05, None)
    assert time.monotonic() - start >= 0.05


def test_run_scenario_stops_and_writes_no_result(tmp_path):
    m = Metrics(collision_count=0, minimum_obstacle_distance_metres=0.4,
                topic_message_counts={"/scan": 20})
    stop = threading.Event()
    stop.set()                                    # already cancelled before the first action
    with pytest.raises(RunStopped):
        run_scenario(_scenario(), FakeRuntime(m), str(tmp_path), stop_event=stop)
    assert list(tmp_path.iterdir()) == []          # a stopped run leaves no artifact
