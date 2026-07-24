from types import SimpleNamespace

from robotbase.container.episode_reader import compact, downsample, image_summary


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


def test_compact_image_returns_bounded_summary_not_pixels():
    msg = SimpleNamespace(width=320, height=240, encoding="rgb8", data=b"\x00" * 230400)
    out = compact("sensor_msgs/msg/Image", msg)
    assert out["width"] == 320 and out["height"] == 240 and out["encoding"] == "rgb8"
    assert "data" not in out                       # never the raw frame
    assert out["mean_rgb"] == [0, 0, 0]
    assert len(out["thumbnail_gray"]) == 8 and len(out["thumbnail_gray"][0]) == 8


def test_compact_image_non_rgb8_skips_thumbnail():
    msg = SimpleNamespace(width=4, height=2, encoding="mono8", data=b"\x00" * 8)
    out = compact("sensor_msgs/msg/Image", msg)
    assert out == {"width": 4, "height": 2, "encoding": "mono8"}


def test_image_summary_captures_brightness():
    # 2x2 rgb8: top row white, bottom row black — thumbnail should reflect the split.
    white, black = bytes([255, 255, 255]), bytes([0, 0, 0])
    msg = SimpleNamespace(width=2, height=2, encoding="rgb8", data=white * 2 + black * 2)
    out = image_summary(msg, n=2)
    assert out["mean_rgb"] == [127, 127, 127]
    assert out["thumbnail_gray"][0] == [255, 255]   # top row bright
    assert out["thumbnail_gray"][1] == [0, 0]       # bottom row dark


def test_compact_contacts_reports_count():
    msg = SimpleNamespace(contacts=[SimpleNamespace(), SimpleNamespace()])
    assert compact("ros_gz_interfaces/msg/Contacts", msg) == {"num_contacts": 2}
