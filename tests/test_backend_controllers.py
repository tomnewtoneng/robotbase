from robotbase.robotspec.semantic import Controller
from robotbase.robotspec.backends.urdf import render_plugin, render_controllers


def test_render_controllers_empty_is_blank():
    assert render_controllers([]) == ""


def test_diff_drive_group_matches_current_bytes():
    diff = Controller("diff-drive", {
        "left_joint": "left_wheel_joint", "right_joint": "right_wheel_joint",
        "wheel_separation": 0.34, "wheel_radius": 0.05, "topic": "cmd_vel",
        "odom_topic": "odom", "tf_topic": "tf", "frame_id": "odom",
        "child_frame_id": "base_footprint", "odom_publish_frequency": 30})
    jsp = Controller("joint-state-publisher", {"topic": "joint_states"})
    assert render_controllers([diff, jsp]) == (
        '\n  <gazebo>'
        '\n    <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">'
        '\n      <left_joint>left_wheel_joint</left_joint><right_joint>right_wheel_joint</right_joint>'
        '\n      <wheel_separation>0.34</wheel_separation><wheel_radius>0.05</wheel_radius>'
        '\n      <topic>cmd_vel</topic><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>'
        '\n      <frame_id>odom</frame_id><child_frame_id>base_footprint</child_frame_id>'
        '\n      <odom_publish_frequency>30</odom_publish_frequency></plugin>'
        '\n    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">'
        '\n      <topic>joint_states</topic></plugin></gazebo>')


def test_joint_position_gains_render_as_str():
    c = Controller("joint-position",
                   {"joint_name": "shoulder_joint", "topic": "shoulder_cmd", "p": 80, "i": 2.0, "d": 8.0},
                   joint="shoulder_joint")
    assert render_plugin(c) == (
        '\n    <plugin filename="gz-sim-joint-position-controller-system" name="gz::sim::systems::JointPositionController">'
        '\n      <joint_name>shoulder_joint</joint_name><topic>shoulder_cmd</topic>'
        '\n      <p_gain>80</p_gain><i_gain>2.0</i_gain><d_gain>8.0</d_gain></plugin>')


def test_velocity_and_odometry_publisher():
    vel = Controller("velocity", {"topic": "cmd_vel"})
    odom = Controller("odometry-publisher", {
        "odom_frame": "odom", "robot_base_frame": "base_link", "dimensions": 3,
        "odom_topic": "odom", "tf_topic": "tf", "odom_publish_frequency": 30})
    assert render_controllers([vel, odom]) == (
        '\n  <gazebo>'
        '\n    <plugin filename="gz-sim-velocity-control-system" name="gz::sim::systems::VelocityControl">'
        '\n      <topic>cmd_vel</topic></plugin>'
        '\n    <plugin filename="gz-sim-odometry-publisher-system" name="gz::sim::systems::OdometryPublisher">'
        '\n      <odom_frame>odom</odom_frame><robot_base_frame>base_link</robot_base_frame>'
        '\n      <dimensions>3</dimensions><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>'
        '\n      <odom_publish_frequency>30</odom_publish_frequency></plugin></gazebo>')
