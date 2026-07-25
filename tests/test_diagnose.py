from robotbase.diagnose import collision_time, diagnose


def _result(scenario, passed, assertions, metrics=None):
    return {"scenario": scenario, "passed": passed, "metrics": metrics or {},
            "assertions": assertions}


def test_passed_run_has_nothing_to_diagnose():
    d = diagnose(_result("drive-forward", True, []), [])
    assert d["passed"] is True
    assert "nothing to diagnose" in d["summary"]


def test_collision_failure_uses_events_and_control():
    result = _result(
        "stop-before-obstacle", False,
        [{"type": "no_contact", "passed": False, "expected": 0, "actual": 1},
         {"type": "minimum_obstacle_distance", "passed": False, "expected": 0.25, "actual": 0.08}],
        metrics={"contact_count": 1},
    )
    events = [
        {"type": "collision", "timestamp": 8.1, "detail": "contact sensor triggered (ground truth)"},
        {"type": "closest_approach", "timestamp": 9.5, "detail": "closest obstacle distance 0.08 m",
         "position": [2.0, 0.0]},
    ]
    d = diagnose(result, events, control_at_failure={"vx": 0.3, "wz": 0.0})
    assert d["passed"] is False
    assert d["failed_assertions"] == ["no_contact", "minimum_obstacle_distance"]
    joined = " ".join(d["findings"])
    assert "Collided at t=8.1s" in joined
    assert "0.08 m of an obstacle near [2.0, 0.0]" in joined
    assert "still commanding forward velocity (vx=0.3" in joined
    assert d["summary"].startswith("stop-before-obstacle failed:")


def test_reach_pose_failure_reports_distance_and_position():
    result = _result(
        "reach-goal", False,
        [{"type": "robot_reached_pose", "passed": False, "expected": 0.35, "actual": 2.76}],
        metrics={"final_x": 4.31, "final_y": -0.0},
    )
    d = diagnose(result, [])
    assert "2.76 m from the goal at (4.31, -0.0)" in d["findings"][0]


def test_collision_time_helper():
    assert collision_time([{"type": "collision", "timestamp": 3.2}]) == 3.2
    assert collision_time([{"type": "stopped", "timestamp": 5.0}]) is None
