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
