from robotbase.robotspec.ir import Fragment
from robotbase.robotspec.modules import MODULES, differential_drive
from robotbase.robotspec.merge import merge_and_render


def _params():
    return {"body": {"shape": "box", "size": [0.35, 0.30, 0.15], "mass": 5.0},
            "drive": {"wheel_radius": 0.05, "wheel_separation": 0.34}}


def test_diff_drive_fragment_shape():
    f = differential_drive(_params(), None)
    assert isinstance(f, Fragment)
    assert f.exposes == ["base_link"]
    assert f.control["velocity_topic"] == "/cmd_vel"
    assert f.ready_topics == ["/odom"]
    assert f.fixed_base is False
    args = [b.arg for b in f.bridges]
    assert "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist" in args
    assert "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry" in args


def test_diff_drive_renders_expected_tokens():
    urdf, *_ = merge_and_render("warehouse_bot", "base_footprint", [differential_drive(_params(), None)])
    for tok in ("base_footprint", "base_link", "left_wheel_joint", "right_wheel_joint",
                "caster", "gz-sim-diff-drive-system", "<wheel_radius>0.05</wheel_radius>"):
        assert tok in urdf, tok


def test_registered_in_modules():
    assert "differential-drive" in MODULES
