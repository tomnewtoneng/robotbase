from robotbase.eval_stats import wilson_ci, is_randomized, aggregate_metrics
from robotbase.schema import RandomizeSpec, PoseJitter


def test_wilson_ci_known_values():
    lo, hi = wilson_ci(8, 10)
    assert round(lo, 2) == 0.49 and round(hi, 2) == 0.94


def test_wilson_ci_all_pass_upper_is_one():
    lo, hi = wilson_ci(10, 10)
    assert hi == 1.0 and lo < 1.0


def test_wilson_ci_zero_n():
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_is_randomized_true_when_any_jitter_nonzero():
    assert is_randomized(RandomizeSpec(robot_pose=PoseJitter(x=0.2))) is True
    assert is_randomized(RandomizeSpec(obstacles=PoseJitter(y=0.3))) is True


def test_is_randomized_false_when_all_zero():
    assert is_randomized(RandomizeSpec()) is False


def test_aggregate_metrics_numeric_only():
    rows = [
        {"distance_travelled_metres": 2.0, "collision_count": 0, "topic_message_counts": {"/scan": 5}},
        {"distance_travelled_metres": 3.0, "collision_count": 1, "topic_message_counts": {"/scan": 6}},
    ]
    agg = aggregate_metrics(rows)
    assert agg["distance_travelled_metres"]["mean"] == 2.5
    assert agg["distance_travelled_metres"]["min"] == 2.0 and agg["distance_travelled_metres"]["max"] == 3.0
    assert agg["distance_travelled_metres"]["count"] == 2
    assert agg["distance_travelled_metres"]["std"] == 0.5   # population std
    assert "topic_message_counts" not in agg                # dict value skipped


def test_aggregate_metrics_std_null_single_trial():
    agg = aggregate_metrics([{"distance_travelled_metres": 2.0}])
    assert agg["distance_travelled_metres"]["std"] is None
