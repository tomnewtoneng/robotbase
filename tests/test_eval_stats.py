from robotbase.eval_stats import (
    wilson_ci, is_randomized, aggregate_metrics, eval_report, suite_eval_report, render_markdown,
)
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


def test_is_randomized_fixed_base_ignores_robot_pose():
    # a fixed-base robot's pose jitter is a no-op (runtime ignores set_robot_pose); only
    # obstacle jitter makes trials actually vary. This is the arm's reach-configuration case:
    # it declares robot_pose jitter for schema conformance but the trials are identical.
    assert is_randomized(RandomizeSpec(robot_pose=PoseJitter(x=0.2)), fixed_base=True) is False
    assert is_randomized(RandomizeSpec(obstacles=PoseJitter(x=0.2)), fixed_base=True) is True


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


def _pt(index, passed, dist):
    return {"index": index, "seed": 100 + index, "run_id": f"run_{index}",
            "passed": passed, "metrics": {"distance_travelled_metres": dist}}


def test_eval_report_randomized_has_ci():
    r = eval_report("drive-forward", [_pt(0, True, 2.0), _pt(1, True, 2.2), _pt(2, False, 0.1)], True)
    assert r["scenario"] == "drive-forward" and r["n"] == 3 and r["passed"] == 2
    assert r["success_rate"] == round(2 / 3, 4)
    assert r["randomized"] is True and r["deterministic"] is False
    assert isinstance(r["ci95"], list) and len(r["ci95"]) == 2
    assert [t["seed"] for t in r["per_trial"]] == [100, 101, 102]
    assert r["metrics"]["distance_travelled_metres"]["count"] == 3


def test_eval_report_deterministic_has_no_ci():
    r = eval_report("reach-configuration", [_pt(0, True, 0.0), _pt(1, True, 0.0)], False)
    assert r["deterministic"] is True and r["ci95"] is None
    assert r["success_rate"] == 1.0


def test_suite_eval_report_sorts_worst_first():
    a = eval_report("a", [_pt(0, True, 1.0), _pt(1, True, 1.0)], True)
    b = eval_report("b", [_pt(0, True, 1.0), _pt(1, False, 0.0)], True)
    s = suite_eval_report([a, b])
    assert s["scenarios"] == 2 and s["results"][0]["scenario"] == "b"
    assert s["mean_success_rate"] == round((1.0 + 0.5) / 2, 4)


def test_render_markdown_single_shows_ci_and_seed():
    r = {"eval_id": "eval_x", "config": {"scenario": "drive-forward", "trials": 3, "seed": 0},
         **eval_report("drive-forward", [_pt(0, True, 2.0), _pt(1, True, 2.2), _pt(2, False, 0.1)], True)}
    md = render_markdown(r)
    assert "drive-forward" in md and "Success rate" in md and "CI" in md and "seed" in md.lower()


def test_render_markdown_deterministic_notes_it():
    r = {"eval_id": "eval_y", "config": {"scenario": "reach-configuration", "trials": 2, "seed": 0},
         **eval_report("reach-configuration", [_pt(0, True, 0.0), _pt(1, True, 0.0)], False)}
    md = render_markdown(r)
    head = md.split("Metrics")[0]
    assert "eterministic" in md and "CI (Wilson)" not in head
