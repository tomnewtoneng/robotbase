import pytest
from robotbase.robotspec.sensors import Ctx, SENSORS, UnknownSensor


CTX = Ctx(world="warehouse", robot_name="warehouse_bot", body_size=[0.35, 0.30, 0.15])


def test_lidar_mounts_to_given_link_and_bridges_scan():
    f = SENSORS["lidar"]({}, "mast", CTX)
    assert any('type="gpu_lidar"' in g for g in f.gazebo)
    assert any(j.parent == "mast" and j.child == "lidar_link" for j in f.joints)
    assert [b.arg for b in f.bridges] == ["/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan"]
    assert f.world_systems == ["gz-sim-sensors-system"]
    assert f.ready_topics == ["/scan"]
    assert "lidar" in f.manifest_sensors


def test_contact_remaps_scoped_topic_to_bumper():
    f = SENSORS["contact"]({}, "base_link", CTX)
    assert f.world_systems == ["gz-sim-contact-system"]
    remap = f.bridges[0].remap
    assert remap[1] == "/bumper" and "sensor/bumper/contact" in remap[0]
    assert "base_footprint_fixed_joint_lump__base_link_collision" in f.gazebo[0]


def test_imu_default_topic_and_system():
    f = SENSORS["imu"]({}, "base_link", CTX)
    assert [b.arg for b in f.bridges] == ["/imu@sensor_msgs/msg/Imu[gz.msgs.IMU"]
    assert f.world_systems == ["gz-sim-imu-system"]


def test_unknown_sensor_key_absent():
    assert "radar" not in SENSORS


def test_sensor_on_nonbase_link_defaults_to_zero_offset():
    from robotbase.robotspec.sensors import Ctx, SENSORS
    ctx = Ctx(world="w", robot_name="r", body_size=[0.35, 0.30, 0.15], base_link="base_link")
    on_base = SENSORS["lidar"]({}, "base_link", ctx).joints[0].xyz
    on_mast = SENSORS["lidar"]({}, "mast", ctx).joints[0].xyz
    assert on_mast == "0 0 0"          # non-base link -> zero offset
    assert on_base != "0 0 0"          # base link -> the tuned default offset


def test_camera_and_depth_emitters():
    from robotbase.robotspec.sensors import SENSORS, Ctx
    ctx = Ctx(world="warehouse", robot_name="camera_bot", body_size=[0.35, 0.30, 0.15])
    cam = SENSORS["camera"]({"resolution": [320, 240]}, "base_link", ctx)
    assert any('type="camera"' in g for g in cam.gazebo)
    assert [b.arg for b in cam.bridges] == ["/image@sensor_msgs/msg/Image[gz.msgs.Image"]
    assert cam.world_systems == ["gz-sim-sensors-system"]
    assert any(j.parent == "base_link" and j.child == "camera_link" for j in cam.joints)

    dep = SENSORS["depth"]({"resolution": [320, 240]}, "base_link", ctx)
    assert any('type="depth_camera"' in g for g in dep.gazebo)
    args = [b.arg for b in dep.bridges]
    assert "/depth@sensor_msgs/msg/Image[gz.msgs.Image" in args
    assert "/depth/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked" in args
    assert dep.world_systems == ["gz-sim-sensors-system"]
