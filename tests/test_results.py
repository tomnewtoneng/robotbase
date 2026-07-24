import json
from robotbase.results import Metrics, AssertionResult, ScenarioResult, new_run_id

def test_run_id_unique():
    assert new_run_id() != new_run_id()

def test_passed_is_conjunction():
    r = ScenarioResult(
        run_id="run_x", scenario="s",
        metrics=Metrics(collision_count=0, minimum_obstacle_distance_metres=0.4,
                        distance_travelled_metres=2.0, final_linear_velocity=0.0,
                        final_angular_velocity=0.0, topic_message_counts={"/scan": 20}),
        assertions=[AssertionResult(type="no_collision", passed=True),
                    AssertionResult(type="robot_stopped", passed=False)],
    )
    assert r.passed is False

def test_result_reports_only_measured_metrics():
    # An arm run measures only joint_positions — the result must not be cluttered with
    # mobile-base fields (final_x, collision_count, ...) that the collector never set.
    arm = ScenarioResult(
        run_id="run_a", scenario="reach-configuration",
        metrics=Metrics(joint_positions={"shoulder_joint": 1.0},
                        topic_message_counts={"/joint_states": 9}),
        assertions=[AssertionResult(type="joint_positions_reached", passed=True)],
    )
    keys = set(arm.model_dump()["metrics"].keys())
    assert keys == {"joint_positions", "topic_message_counts"}
    assert "final_x" not in keys and "collision_count" not in keys

    # A mobile run keeps its measured fields, including a meaningful collision_count of 0.
    mobile = ScenarioResult(
        run_id="run_m", scenario="stop-before-obstacle",
        metrics=Metrics(collision_count=0, contact_count=0, distance_travelled_metres=2.0,
                        topic_message_counts={"/scan": 20}),
        assertions=[AssertionResult(type="no_contact", passed=True)],
    )
    mkeys = set(mobile.model_dump()["metrics"].keys())
    assert "collision_count" in mkeys and "distance_travelled_metres" in mkeys
    assert "joint_positions" not in mkeys


def test_write_creates_json(tmp_path):
    r = ScenarioResult(run_id="run_y", scenario="s",
                       metrics=Metrics(collision_count=0, minimum_obstacle_distance_metres=None,
                                       distance_travelled_metres=1.0, final_linear_velocity=0.0,
                                       final_angular_velocity=0.0, topic_message_counts={}),
                       assertions=[AssertionResult(type="no_collision", passed=True)])
    path = r.write(str(tmp_path))
    data = json.loads(open(path).read())
    assert data["run_id"] == "run_y"
    assert data["passed"] is True
