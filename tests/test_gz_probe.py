from robotbase.robotbench.gz_probe import parse_model_xy, sample_model_pose, cmd_vel_is_live

DUMP = '''pose {
  name: "robot"
  id: 29
  position {
    x: 1.5
    y: -0.25
    z: 0.05
  }
  orientation { w: 1 }
}
pose {
  name: "base_footprint"
  id: 30
  position { }
  orientation { w: 1 }
}
'''


def test_parses_model_world_xy():
    assert parse_model_xy(DUMP, "robot") == (1.5, -0.25)


def test_missing_model_returns_none():
    assert parse_model_xy(DUMP, "ghost") is None


def test_missing_coords_default_to_zero():
    # gz omits ~0 fields: base_footprint has an empty position block -> (0.0, 0.0)
    assert parse_model_xy(DUMP, "base_footprint") == (0.0, 0.0)


def test_sample_collects_trace_via_injected_sh():
    calls = {"n": 0}
    def sh(_cmd):
        calls["n"] += 1
        return DUMP
    trace = sample_model_pose("robot", duration_s=0.25, sh=sh, hz=50)
    assert trace and all(pt[1:] == (1.5, -0.25) for pt in trace)
    assert trace[0][0] >= 0.0


def test_cmd_vel_is_live_checks_required_interfaces():
    sh = lambda _c: "/cmd_vel\n/scan\n/odom\n/clock"
    assert cmd_vel_is_live(sh, ["scan"]) is True
    assert cmd_vel_is_live(sh, ["scan", "image"]) is False   # /image missing
