"""Archetype modules — each emits a Fragment of semantic parts (see declarative-compiler.md)."""
from __future__ import annotations

from robotbase.robotspec.ir import Bridge, Fragment, body_xyz
from robotbase.robotspec.semantic import Inertial, Joint, RigidBody


class UnknownArchetype(ValueError):
    ...


def differential_drive(params: dict, mount: dict | None) -> Fragment:
    body = params.get("body", {})
    drive = params.get("drive", {})
    bx, by, bz = body_xyz(body.get("size", [0.35, 0.30, 0.15]), body.get("shape", "box"))
    m = body.get("mass", 5.0)
    wr = drive.get("wheel_radius", 0.05)
    ws = drive.get("wheel_separation", 0.34)
    f = Fragment(exposes=["base_link"], control={"velocity_topic": "/cmd_vel"},
                 ready_topics=["/odom"], fixed_base=False)

    f.links.append(RigidBody("base_footprint"))
    f.links.append(RigidBody("base_link", ("box", [bx, by, bz]), mass=m))
    f.joints.append(Joint("base_joint", "fixed", "base_footprint", "base_link",
                          xyz=f"0 0 {wr + bz/2}"))

    def wheel(name, y):
        f.links.append(RigidBody(name, ("cylinder", [wr, 0.04]),
                                 inertia=Inertial(0.5, 0.001, 0.001, 0.001),
                                 collision_origin='rpy="1.5708 0 0"', visual_origin='rpy="1.5708 0 0"',
                                 material="black", rgba="0.1 0.1 0.1 1"))
        f.joints.append(Joint(f"{name}_joint", "continuous", "base_link", name,
                              xyz=f"-0.05 {y} {-bz/2}", axis="0 1 0"))
    wheel("left_wheel", ws / 2)
    wheel("right_wheel", -ws / 2)

    f.links.append(RigidBody("caster", ("sphere", [wr]),
                             inertia=Inertial(0.1, 0.0001, 0.0001, 0.0001),
                             friction=(0.0, 0.0), material=None))
    f.joints.append(Joint("caster_joint", "fixed", "base_link", "caster",
                          xyz=f"{bx/2 - wr} 0 {-bz/2}"))

    f.gazebo.append(
        '\n  <gazebo>'
        '\n    <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">'
        '\n      <left_joint>left_wheel_joint</left_joint><right_joint>right_wheel_joint</right_joint>'
        f'\n      <wheel_separation>{ws}</wheel_separation><wheel_radius>{wr}</wheel_radius>'
        '\n      <topic>cmd_vel</topic><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>'
        '\n      <frame_id>odom</frame_id><child_frame_id>base_footprint</child_frame_id>'
        '\n      <odom_publish_frequency>30</odom_publish_frequency></plugin>'
        '\n    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">'
        '\n      <topic>joint_states</topic></plugin></gazebo>'
        '\n  <gazebo reference="left_wheel"><mu1>1.0</mu1><mu2>1.0</mu2></gazebo>'
        '\n  <gazebo reference="right_wheel"><mu1>1.0</mu1><mu2>1.0</mu2></gazebo>'
        '\n  <gazebo reference="caster"><mu1>0.0</mu1><mu2>0.0</mu2></gazebo>')

    f.bridges += [
        Bridge("/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist"),
        Bridge("/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry"),
        Bridge("/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V"),
        Bridge("/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model"),
        Bridge("/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"),
    ]
    return f


def arm(params: dict, mount: dict | None) -> Fragment:
    LINK_LEN, LINK_RAD = 0.40, 0.035
    f = Fragment(exposes=["tip"],
                 control={"joint_command_topics": ["/shoulder_cmd", "/elbow_cmd"]},
                 ready_topics=["/joint_states"])

    # Anchor: standalone -> the gz `world` frame; mounted -> the given link (mobile manipulator).
    if mount is None:
        f.links.append(RigidBody("world"))
        f.joints.append(Joint("arm_fixed_base", "fixed", "world", "arm_base_link", xyz="0 0 0.05"))
        f.fixed_base = True
    else:
        to = mount.get("to", "base_link")
        xyz = " ".join(str(v) for v in mount.get("xyz", [0, 0, 0]))
        rpy = " ".join(str(v) for v in mount.get("rpy", [0, 0, 0]))
        f.joints.append(Joint("arm_mount", "fixed", to, "arm_base_link", xyz=xyz, rpy=rpy))
        # mounted on a mobile base: leave fixed_base None so the base's value (False) wins

    f.links.append(RigidBody("arm_base_link", ("cylinder", [0.07, 0.10]),
                             inertia=Inertial(10.0, 0.05, 0.05, 0.05),
                             material="arm_base", rgba="0.25 0.25 0.30 1"))

    def arm_link(name, rgba):
        origin = f'xyz="0 0 {LINK_LEN/2}"'
        f.links.append(RigidBody(name, ("cylinder", [LINK_RAD, LINK_LEN]),
                                 inertia=Inertial(0.15, 0.002, 0.002, 0.0002),
                                 inertial_origin=origin, collision_origin=origin, visual_origin=origin,
                                 material=f"{name}_mat", rgba=rgba))
    arm_link("upper_arm", "0.2 0.5 0.8 1")
    arm_link("forearm", "0.2 0.7 0.5 1")

    f.joints.append(Joint("shoulder_joint", "revolute", "arm_base_link", "upper_arm",
                          xyz="0 0 0.05", axis="0 1 0", limit=("-3.14", "3.14", "100", "3.0")))
    f.joints.append(Joint("elbow_joint", "revolute", "upper_arm", "forearm",
                          xyz=f"0 0 {LINK_LEN}", axis="0 1 0", limit=("-3.14", "3.14", "100", "3.0")))
    f.links.append(RigidBody("tip"))
    f.joints.append(Joint("tip_joint", "fixed", "forearm", "tip", xyz=f"0 0 {LINK_LEN}"))

    f.gazebo.append(
        '\n  <gazebo>'
        '\n    <plugin filename="gz-sim-joint-position-controller-system" name="gz::sim::systems::JointPositionController">'
        '\n      <joint_name>shoulder_joint</joint_name><topic>shoulder_cmd</topic>'
        '\n      <p_gain>80</p_gain><i_gain>2.0</i_gain><d_gain>8.0</d_gain></plugin>'
        '\n    <plugin filename="gz-sim-joint-position-controller-system" name="gz::sim::systems::JointPositionController">'
        '\n      <joint_name>elbow_joint</joint_name><topic>elbow_cmd</topic>'
        '\n      <p_gain>60</p_gain><i_gain>2.0</i_gain><d_gain>6.0</d_gain></plugin>'
        '\n    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">'
        '\n      <topic>joint_states</topic></plugin></gazebo>')

    f.bridges += [
        Bridge("/shoulder_cmd@std_msgs/msg/Float64]gz.msgs.Double"),
        Bridge("/elbow_cmd@std_msgs/msg/Float64]gz.msgs.Double"),
        Bridge("/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model"),
        Bridge("/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"),
    ]
    return f


def quadrotor(params: dict, mount: dict | None) -> Fragment:
    body = params.get("body", {})
    bx, by, bz = body_xyz(body.get("size", [0.16, 0.16, 0.06]), body.get("shape", "box"))
    m = body.get("mass", 1.0)
    ARM = 0.18
    f = Fragment(exposes=["base_link"], control={"velocity_topic": "/cmd_vel"},
                 ready_topics=["/odom"], fixed_base=False)

    f.links.append(RigidBody("base_link", ("box", [bx, by, bz]),
                             inertia=Inertial(m, 0.02, 0.02, 0.04),
                             material="body", rgba="0.2 0.2 0.25 1"))

    def rotor(name, x, y, rgba):
        f.links.append(RigidBody(name, ("cylinder", [0.05, 0.01]),
                                 inertia=Inertial(0.02, 1e-5, 1e-5, 1e-5),
                                 has_collision=False, material=f"{name}_m", rgba=rgba))
        f.joints.append(Joint(f"{name}_joint", "fixed", "base_link", name, xyz=f"{x} {y} 0.04"))
    rotor("rotor_fl", ARM, ARM, "0.9 0.2 0.2 1")
    rotor("rotor_fr", ARM, -ARM, "0.2 0.2 0.2 1")
    rotor("rotor_bl", -ARM, ARM, "0.2 0.2 0.2 1")
    rotor("rotor_br", -ARM, -ARM, "0.2 0.2 0.2 1")

    f.gazebo.append(
        '\n  <gazebo>'
        '\n    <plugin filename="gz-sim-velocity-control-system" name="gz::sim::systems::VelocityControl">'
        '\n      <topic>cmd_vel</topic></plugin>'
        '\n    <plugin filename="gz-sim-odometry-publisher-system" name="gz::sim::systems::OdometryPublisher">'
        '\n      <odom_frame>odom</odom_frame><robot_base_frame>base_link</robot_base_frame>'
        '\n      <dimensions>3</dimensions><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>'
        '\n      <odom_publish_frequency>30</odom_publish_frequency></plugin></gazebo>')

    f.bridges += [
        Bridge("/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist"),
        Bridge("/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry"),
        Bridge("/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V"),
        Bridge("/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"),
    ]
    return f


MODULES = {"differential-drive": differential_drive, "arm": arm, "quadrotor": quadrotor}
