from robotbase.recording import (
    episode_events,
    episode_sidecar,
    record_command,
    record_selection,
)
from robotbase.results import Metrics, ScenarioResult
from robotbase.schema import Scenario


AVAILABLE = ["/scan", "/odom", "/cmd_vel", "/image", "/clock"]


def test_selection_defaults_to_all_available():
    assert record_selection([], [], AVAILABLE) == AVAILABLE


def test_selection_honours_allow_list():
    assert record_selection(["/scan", "/odom"], [], AVAILABLE) == ["/scan", "/odom"]


def test_selection_applies_exclude_to_allow_list():
    assert record_selection(["/scan", "/image"], ["/image"], AVAILABLE) == ["/scan"]


def test_selection_applies_exclude_to_all():
    assert record_selection([], ["/image"], AVAILABLE) == ["/scan", "/odom", "/cmd_vel", "/clock"]


def test_selection_falls_back_to_dash_a_when_nothing_known():
    assert record_selection([], [], []) == ["-a"]


def test_record_command_uses_mcap_and_sim_time():
    cmd = record_command("/ws/.robotbase/current/episode", ["/scan", "/odom"])
    assert "ros2 bag record" in cmd
    assert "--storage mcap" in cmd
    assert "--use-sim-time" in cmd
    assert "-o /ws/.robotbase/current/episode" in cmd
    assert cmd.startswith("rm -rf /ws/.robotbase/current/episode")  # stale staging cleared
    assert "/scan /odom" in cmd


def _result(collision: int) -> ScenarioResult:
    return ScenarioResult(
        run_id="run_test123456",
        scenario="stop-before-obstacle",
        metrics=Metrics(collision_count=collision, minimum_obstacle_distance_metres=0.3),
        assertions=[],
    )


def test_events_report_collision():
    assert episode_events(_result(1))[0]["type"] == "collision"
    assert episode_events(_result(0)) == []


def test_sidecar_is_self_describing():
    scenario = Scenario(version=1, name="stop-before-obstacle")
    sidecar = episode_sidecar(scenario, _result(0), {"mcap": "episode.mcap", "topics": ["/scan"]})
    assert sidecar["version"] == 1
    assert sidecar["run_id"] == "run_test123456"
    assert sidecar["recording"]["mcap"] == "episode.mcap"
    assert sidecar["recording"]["storage"] == "mcap"
    assert sidecar["recording"]["topics"] == ["/scan"]
    assert sidecar["scenario_spec"]["name"] == "stop-before-obstacle"
    assert "result" in sidecar


def test_sidecar_handles_no_recording():
    scenario = Scenario(version=1, name="drive-forward")
    sidecar = episode_sidecar(scenario, _result(0), None)
    assert sidecar["recording"]["mcap"] is None
    assert sidecar["recording"]["topics"] == []
