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
