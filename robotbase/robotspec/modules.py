"""Archetype modules — each emits a Fragment (see docs/design/declarative-compiler.md)."""
from __future__ import annotations

from robotbase.robotspec.ir import Bridge, Fragment, JointIR, LinkIR, link_from_shape


class UnknownArchetype(ValueError):
    ...


def differential_drive(params: dict, mount: dict | None) -> Fragment:
    body = params.get("body", {})
    drive = params.get("drive", {})
    bx, by, bz = body.get("size", [0.35, 0.30, 0.15])
    m = body.get("mass", 5.0)
    wr = drive.get("wheel_radius", 0.05)
    ws = drive.get("wheel_separation", 0.34)
    f = Fragment(exposes=["base_link"], control={"velocity_topic": "/cmd_vel"},
                 ready_topics=["/odom"], fixed_base=False)

    f.links.append(LinkIR("base_footprint", '\n  <link name="base_footprint"/>'))
    f.links.append(link_from_shape("base_link", "box", [bx, by, bz], m))
    f.joints.append(JointIR("base_joint",
        f'\n  <joint name="base_joint" type="fixed"><parent link="base_footprint"/>'
        f'<child link="base_link"/><origin xyz="0 0 {wr + bz/2}"/></joint>',
        parent="base_footprint", child="base_link"))

    def wheel(name, y):
        f.links.append(LinkIR(name,
            f'\n  <link name="{name}">'
            f'<inertial><mass value="0.5"/><inertia ixx="0.001" ixy="0" ixz="0" iyy="0.001" iyz="0" izz="0.001"/></inertial>'
            f'<collision><origin rpy="1.5708 0 0"/><geometry><cylinder radius="{wr}" length="0.04"/></geometry></collision>'
            f'<visual><origin rpy="1.5708 0 0"/><geometry><cylinder radius="{wr}" length="0.04"/></geometry>'
            f'<material name="black"><color rgba="0.1 0.1 0.1 1"/></material></visual></link>'))
        f.joints.append(JointIR(f"{name}_joint",
            f'\n  <joint name="{name}_joint" type="continuous"><parent link="base_link"/>'
            f'<child link="{name}"/><origin xyz="-0.05 {y} {-bz/2}"/><axis xyz="0 1 0"/></joint>',
            parent="base_link", child=name))
    wheel("left_wheel", ws / 2)
    wheel("right_wheel", -ws / 2)

    f.links.append(LinkIR("caster",
        '\n  <link name="caster"><inertial><mass value="0.1"/>'
        '<inertia ixx="0.0001" ixy="0" ixz="0" iyy="0.0001" iyz="0" izz="0.0001"/></inertial>'
        f'<collision><geometry><sphere radius="{wr}"/></geometry>'
        '<surface><friction><ode><mu>0.0</mu><mu2>0.0</mu2></ode></friction></surface></collision>'
        f'<visual><geometry><sphere radius="{wr}"/></geometry></visual></link>'))
    f.joints.append(JointIR("caster_joint",
        f'\n  <joint name="caster_joint" type="fixed"><parent link="base_link"/>'
        f'<child link="caster"/><origin xyz="{bx/2 - wr} 0 {-bz/2}"/></joint>',
        parent="base_link", child="caster"))

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
        f.links.append(LinkIR("world", '\n  <link name="world"/>'))
        f.joints.append(JointIR("arm_fixed_base",
            '\n  <joint name="arm_fixed_base" type="fixed"><parent link="world"/>'
            '<child link="arm_base_link"/><origin xyz="0 0 0.05"/></joint>',
            parent="world", child="arm_base_link"))
        f.fixed_base = True
    else:
        to = mount.get("to", "base_link")
        xyz = " ".join(str(v) for v in mount.get("xyz", [0, 0, 0]))
        rpy = " ".join(str(v) for v in mount.get("rpy", [0, 0, 0]))
        f.joints.append(JointIR("arm_mount",
            f'\n  <joint name="arm_mount" type="fixed"><parent link="{to}"/>'
            f'<child link="arm_base_link"/><origin xyz="{xyz}" rpy="{rpy}"/></joint>',
            parent=to, child="arm_base_link"))
        # mounted on a mobile base: leave fixed_base None so the base's value (False) wins

    f.links.append(LinkIR("arm_base_link",
        '\n  <link name="arm_base_link"><inertial><mass value="10.0"/>'
        '<inertia ixx="0.05" ixy="0" ixz="0" iyy="0.05" iyz="0" izz="0.05"/></inertial>'
        '<collision><geometry><cylinder radius="0.07" length="0.10"/></geometry></collision>'
        '<visual><geometry><cylinder radius="0.07" length="0.10"/></geometry>'
        '<material name="arm_base"><color rgba="0.25 0.25 0.30 1"/></material></visual></link>'))

    def arm_link(name, rgba):
        f.links.append(LinkIR(name,
            f'\n  <link name="{name}"><inertial><origin xyz="0 0 {LINK_LEN/2}"/>'
            '<mass value="0.15"/><inertia ixx="0.002" ixy="0" ixz="0" iyy="0.002" iyz="0" izz="0.0002"/></inertial>'
            f'<collision><origin xyz="0 0 {LINK_LEN/2}"/><geometry><cylinder radius="{LINK_RAD}" length="{LINK_LEN}"/></geometry></collision>'
            f'<visual><origin xyz="0 0 {LINK_LEN/2}"/><geometry><cylinder radius="{LINK_RAD}" length="{LINK_LEN}"/></geometry>'
            f'<material name="{name}_mat"><color rgba="{rgba}"/></material></visual></link>'))
    arm_link("upper_arm", "0.2 0.5 0.8 1")
    arm_link("forearm", "0.2 0.7 0.5 1")

    f.joints.append(JointIR("shoulder_joint",
        '\n  <joint name="shoulder_joint" type="revolute"><parent link="arm_base_link"/>'
        '<child link="upper_arm"/><origin xyz="0 0 0.05"/><axis xyz="0 1 0"/>'
        '<limit lower="-3.14" upper="3.14" effort="100" velocity="3.0"/></joint>',
        parent="arm_base_link", child="upper_arm"))
    f.joints.append(JointIR("elbow_joint",
        f'\n  <joint name="elbow_joint" type="revolute"><parent link="upper_arm"/>'
        f'<child link="forearm"/><origin xyz="0 0 {LINK_LEN}"/><axis xyz="0 1 0"/>'
        '<limit lower="-3.14" upper="3.14" effort="100" velocity="3.0"/></joint>',
        parent="upper_arm", child="forearm"))
    f.links.append(LinkIR("tip", '\n  <link name="tip"/>'))
    f.joints.append(JointIR("tip_joint",
        f'\n  <joint name="tip_joint" type="fixed"><parent link="forearm"/>'
        f'<child link="tip"/><origin xyz="0 0 {LINK_LEN}"/></joint>',
        parent="forearm", child="tip"))

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


MODULES = {"differential-drive": differential_drive, "arm": arm}
