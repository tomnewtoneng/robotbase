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


def test_arm_module_standalone_anchors_to_world():
    from robotbase.robotspec.modules import MODULES
    f = MODULES["arm"]({}, None)
    assert f.fixed_base is True
    assert "tip" in f.exposes
    assert f.ready_topics == ["/joint_states"]
    assert any("JointPositionController" in g for g in f.gazebo)
    assert any(l.name == "world" for l in f.links)                 # world anchor when standalone
    args = [b.arg for b in f.bridges]
    assert "/shoulder_cmd@std_msgs/msg/Float64]gz.msgs.Double" in args
    assert "/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model" in args


def test_arm_renders_the_joint_chain():
    from robotbase.robotspec.modules import MODULES
    from robotbase.robotspec.merge import merge_and_render
    urdf, *_ = merge_and_render("arm_bot", "world", [MODULES["arm"]({}, None)])
    for tok in ("arm_base_link", "upper_arm", "forearm", "shoulder_joint", "elbow_joint", "tip"):
        assert tok in urdf, tok


def test_arm_mounted_attaches_to_link_without_world_anchor():
    from robotbase.robotspec.modules import MODULES
    f = MODULES["arm"]({}, {"to": "base_link", "xyz": [0, 0, 0.15]})
    assert not any(l.name == "world" for l in f.links)             # no world anchor when mounted
    assert any(j.parent == "base_link" and j.child == "arm_base_link" for j in f.joints)
    assert f.fixed_base is None                                    # inherits from the drive base


def test_quadrotor_module():
    from robotbase.robotspec.modules import MODULES
    f = MODULES["quadrotor"]({"body": {"size": [0.16, 0.16, 0.06], "mass": 1.0}}, None)
    assert f.exposes == ["base_link"]
    assert f.control["velocity_topic"] == "/cmd_vel"
    assert f.ready_topics == ["/odom"]
    assert f.fixed_base is False
    assert any("VelocityControl" in g for g in f.gazebo)
    assert any("OdometryPublisher" in g for g in f.gazebo)
    args = [b.arg for b in f.bridges]
    assert "/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist" in args
    assert "/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry" in args


def test_quadrotor_renders_body_and_rotors():
    from robotbase.robotspec.modules import MODULES
    from robotbase.robotspec.merge import merge_and_render
    urdf, *_ = merge_and_render("drone", "base_link", [MODULES["quadrotor"]({}, None)])
    for tok in ("base_link", "rotor_fl", "rotor_fr", "rotor_bl", "rotor_br"):
        assert tok in urdf, tok
