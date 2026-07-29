from robotbase.robotbench.acceptance import SPECS, min_distance_to, spawn_pose


def test_stop_at_1m_passes_when_stopped_in_band():
    spec = SPECS["author_stop_at_1m"]
    trace = [(t * 0.1, x, 0.0) for t, x in enumerate([0.0, 0.4, 0.8, 1.0, 1.05, 1.05, 1.05])]
    assert spec.predicate(trace, spec.world_obstacles) is True     # min gap ~ 0.95 m


def test_stop_at_1m_fails_on_collision():
    spec = SPECS["author_stop_at_1m"]
    trace = [(i * 0.1, i * 0.25, 0.0) for i in range(12)]          # drives into box at x=2
    assert spec.predicate(trace, spec.world_obstacles) is False


def test_mast_clear_requires_pass_low_stop_tall():
    spec = SPECS["author_mast_clear"]
    # passes low barrier at x=2 (gap<0.5), stops ~1 m before tall box at x=3.5
    trace = [(i * 0.1, x, 0.0) for i, x in enumerate([0, 0.5, 1.0, 1.5, 2.0, 2.4, 2.5, 2.5])]
    assert spec.predicate(trace, spec.world_obstacles) is True


def test_spawn_pose_is_deterministic_per_seed():
    spec = SPECS["author_stop_at_1m"]
    assert spawn_pose(spec, 3) == spawn_pose(spec, 3) != spawn_pose(spec, 4)


def test_min_distance_helper():
    assert round(min_distance_to([(0, 0, 0), (0, 1, 0)], 0.0, 3.0), 2) == 2.0
