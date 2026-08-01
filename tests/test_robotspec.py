import pytest

from robotbase.robotspec.compile import UnknownArchetype, UnknownSensor, compile_robot
from robotbase.robotspec.project import render_launch
from robotbase.robotspec.schema import RobotSpec, SensorSpec


def _diff_spec():
    return RobotSpec(name="warehouse_bot", base="differential-drive",
                     sensors=[SensorSpec(type="lidar"), SensorSpec(type="imu"),
                              SensorSpec(type="contact")])


def test_urdf_has_the_chassis_plugins_and_sensors():
    urdf = compile_robot(_diff_spec()).urdf
    for token in ('name="warehouse_bot"', "base_footprint", "base_link", "left_wheel_joint",
                  "right_wheel_joint", "caster", "gz-sim-diff-drive-system", 'type="gpu_lidar"',
                  'type="imu"', 'type="contact"',
                  "base_footprint_fixed_joint_lump__base_link_collision"):
        assert token in urdf, token


def test_bridges_and_the_contact_remap():
    c = compile_robot(_diff_spec())
    args = [b.arg for b in c.bridges]
    assert "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist" in args
    assert "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry" in args
    assert "/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" in args
    assert "/imu@sensor_msgs/msg/Imu[gz.msgs.IMU" in args
    remapped = [b for b in c.bridges if b.remap]
    assert len(remapped) == 1                       # only the contact sensor needs a remap
    assert remapped[0].remap[1] == "/bumper"
    assert "sensor/bumper/contact" in remapped[0].remap[0]


def test_world_systems_and_manifest_are_derived():
    c = compile_robot(_diff_spec())
    assert set(c.world_systems) == {"gz-sim-sensors-system", "gz-sim-imu-system",
                                    "gz-sim-contact-system"}
    assert c.manifest["ready_topics"] == ["/odom", "/scan"]
    assert c.manifest["fixed_base"] is False
    assert c.manifest["control"]["velocity_topic"] == "/cmd_vel"
    assert set(c.manifest["sensors"]) == {"lidar", "imu", "contact"}


def test_body_and_drive_params_flow_into_the_urdf():
    spec = _diff_spec()
    spec.drive.wheel_radius = 0.07
    urdf = compile_robot(spec).urdf
    assert "<wheel_radius>0.07</wheel_radius>" in urdf


def test_render_launch_is_valid_python_and_data_driven():
    launch = render_launch("warehouse_bot")
    assert 'get_package_share_directory("warehouse_bot_description")' in launch
    assert "bridges.json" in launch                  # bridges compiled from sensors, read at launch
    compile(launch, "<launch>", "exec")              # syntactically valid


def test_sensor_wiring_is_compiled_onto_the_robot():
    # the launch is data-driven; the actual sensor wiring lives on the compiled robot's bridges
    c = compile_robot(_diff_spec())
    args = [b.arg for b in c.bridges]
    assert any("/scan@sensor_msgs/msg/LaserScan" in a for a in args)
    assert any(b.remap and b.remap[1] == "/bumper" for b in c.bridges)   # the contact remap target


def test_unknown_archetype_and_sensor_raise():
    with pytest.raises(UnknownArchetype):
        compile_robot(RobotSpec(base="hovercraft"))
    with pytest.raises(UnknownSensor):
        compile_robot(RobotSpec(base="differential-drive", sensors=[SensorSpec(type="radar")]))
