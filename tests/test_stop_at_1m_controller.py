import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location(
    "stop_at_1m",
    pathlib.Path("robotbase/robotbench/fixtures/controllers/stop_at_1m.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test_drives_forward_when_clear():
    lin, ang = m.desired_twist([5.0] * 180)
    assert lin == 0.3 and ang == 0.0


def test_stops_when_obstacle_within_1m():
    ranges = [5.0] * 180
    ranges[90] = 0.8   # dead ahead
    lin, ang = m.desired_twist(ranges)
    assert lin == 0.0


def test_ignores_inf_and_nan():
    lin, _ = m.desired_twist([float("inf"), float("nan"), 5.0])
    assert lin == 0.3
