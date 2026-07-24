from types import SimpleNamespace

from robotbase.container.episode_reader import compact, downsample


def test_downsample_shrinks_to_max_and_keeps_ends():
    items = list(range(100))
    out = downsample(items, 40)
    assert len(out) == 40
    assert out[0] == 0
    assert out[-1] == items[int(39 * (100 / 40))]


def test_downsample_leaves_small_lists_untouched():
    assert downsample([1, 2, 3], 40) == [1, 2, 3]
    assert downsample([1, 2, 3], 0) == [1, 2, 3]


def test_compact_laserscan_reports_bounded_range_stats():
    msg = SimpleNamespace(ranges=[0.5, 99.0, 0.2, -1.0], range_min=0.1, range_max=10.0)
    out = compact("sensor_msgs/msg/LaserScan", msg)
    assert out == {"min_range": 0.2, "num_valid": 2, "num_total": 4}


def test_compact_odometry_extracts_pose_and_twist():
    msg = SimpleNamespace(
        pose=SimpleNamespace(pose=SimpleNamespace(position=SimpleNamespace(x=1.234, y=5.678))),
        twist=SimpleNamespace(twist=SimpleNamespace(
            linear=SimpleNamespace(x=0.3), angular=SimpleNamespace(z=-0.1))),
    )
    out = compact("nav_msgs/msg/Odometry", msg)
    assert out == {"x": 1.234, "y": 5.678, "vx": 0.3, "wz": -0.1}


def test_compact_twist():
    msg = SimpleNamespace(linear=SimpleNamespace(x=0.5), angular=SimpleNamespace(z=0.2))
    assert compact("geometry_msgs/msg/Twist", msg) == {"vx": 0.5, "wz": 0.2}


def test_compact_image_never_returns_pixels():
    msg = SimpleNamespace(width=320, height=240, encoding="rgb8", data=b"\x00" * 230400)
    out = compact("sensor_msgs/msg/Image", msg)
    assert out == {"width": 320, "height": 240, "encoding": "rgb8"}
    assert "data" not in out


def test_compact_contacts_reports_count():
    msg = SimpleNamespace(contacts=[SimpleNamespace(), SimpleNamespace()])
    assert compact("ros_gz_interfaces/msg/Contacts", msg) == {"num_contacts": 2}
