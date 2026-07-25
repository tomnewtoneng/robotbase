"""Compile a RobotSpec into the concrete ROS/Gazebo artifacts (see docs/design/robot-spec.md).

Composable: an *archetype* (`base`) builds the chassis + control plugin + runtime facts, and
each *sensor* contributes a link + a gz sensor + a bridge + the world system it needs. The
compiler owns every sim gotcha (collision-lump naming, the contact scoped topic, deriving
world systems, bridge types) so the spec stays about intent.

Phase 1: the `differential-drive` archetype with the `lidar`, `imu`, `contact` sensors.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from robotbase.robotspec.schema import RobotSpec, SensorSpec


@dataclass
class Bridge:
    arg: str                                  # a parameter_bridge argument
    remap: tuple[str, str] | None = None      # (from, to) when the gz topic != the ROS topic


@dataclass
class CompiledRobot:
    name: str
    urdf: str                                 # a complete .urdf.xacro (plain URDF; xacro passes it through)
    bridges: list[Bridge]
    world_systems: list[str]                  # gz system plugin filenames the world must load
    manifest: dict                            # sensors / ready_topics / fixed_base / control / robot
    spawn_z: float = 0.1


class UnknownArchetype(ValueError):
    ...


class UnknownSensor(ValueError):
    ...


# ---- differential-drive archetype -------------------------------------------

def _differential_drive(spec: RobotSpec):
    bx, by, bz = spec.body.size
    wr, ws, m = spec.drive.wheel_radius, spec.drive.wheel_separation, spec.body.mass

    def wheel(name, y):
        return f'''
  <link name="{name}">
    <inertial><mass value="0.5"/><inertia ixx="0.001" ixy="0" ixz="0" iyy="0.001" iyz="0" izz="0.001"/></inertial>
    <collision><origin rpy="1.5708 0 0"/><geometry><cylinder radius="{wr}" length="0.04"/></geometry></collision>
    <visual><origin rpy="1.5708 0 0"/><geometry><cylinder radius="{wr}" length="0.04"/></geometry><material name="black"><color rgba="0.1 0.1 0.1 1"/></material></visual>
  </link>
  <joint name="{name}_joint" type="continuous">
    <parent link="base_link"/><child link="{name}"/>
    <origin xyz="-0.05 {y} {-bz / 2}"/><axis xyz="0 1 0"/>
  </joint>'''

    links = f'''
  <link name="base_footprint"/>
  <link name="base_link">
    <inertial><mass value="{m}"/><inertia ixx="0.08" ixy="0" ixz="0" iyy="0.10" iyz="0" izz="0.10"/></inertial>
    <collision><geometry><box size="{bx} {by} {bz}"/></geometry></collision>
    <visual><geometry><box size="{bx} {by} {bz}"/></geometry><material name="grey"><color rgba="0.4 0.4 0.45 1"/></material></visual>
  </link>
  <joint name="base_joint" type="fixed">
    <parent link="base_footprint"/><child link="base_link"/><origin xyz="0 0 {wr + bz / 2}"/>
  </joint>
{wheel("left_wheel", ws / 2)}
{wheel("right_wheel", -ws / 2)}
  <link name="caster">
    <inertial><mass value="0.1"/><inertia ixx="0.0001" ixy="0" ixz="0" iyy="0.0001" iyz="0" izz="0.0001"/></inertial>
    <collision><geometry><sphere radius="{wr}"/></geometry><surface><friction><ode><mu>0.0</mu><mu2>0.0</mu2></ode></friction></surface></collision>
    <visual><geometry><sphere radius="{wr}"/></geometry></visual>
  </link>
  <joint name="caster_joint" type="fixed">
    <parent link="base_link"/><child link="caster"/><origin xyz="{bx / 2 - wr} 0 {-bz / 2}"/>
  </joint>'''

    plugins = f'''
  <gazebo>
    <plugin filename="gz-sim-diff-drive-system" name="gz::sim::systems::DiffDrive">
      <left_joint>left_wheel_joint</left_joint><right_joint>right_wheel_joint</right_joint>
      <wheel_separation>{ws}</wheel_separation><wheel_radius>{wr}</wheel_radius>
      <topic>cmd_vel</topic><odom_topic>odom</odom_topic><tf_topic>tf</tf_topic>
      <frame_id>odom</frame_id><child_frame_id>base_footprint</child_frame_id>
      <odom_publish_frequency>30</odom_publish_frequency>
    </plugin>
    <plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">
      <topic>joint_states</topic>
    </plugin>
  </gazebo>
  <gazebo reference="left_wheel"><mu1>1.0</mu1><mu2>1.0</mu2></gazebo>
  <gazebo reference="right_wheel"><mu1>1.0</mu1><mu2>1.0</mu2></gazebo>
  <gazebo reference="caster"><mu1>0.0</mu1><mu2>0.0</mu2></gazebo>'''

    bridges = [
        Bridge("/cmd_vel@geometry_msgs/msg/Twist]gz.msgs.Twist"),
        Bridge("/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry"),
        Bridge("/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V"),
        Bridge("/joint_states@sensor_msgs/msg/JointState[gz.msgs.Model"),
        Bridge("/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"),
    ]
    manifest = {
        "control": {"velocity_topic": "/cmd_vel"},
        "ready_topics": ["/odom"],
        "fixed_base": False,
    }
    return links, plugins, bridges, manifest, 0.1


ARCHETYPES = {"differential-drive": _differential_drive}


# ---- sensor modules ---------------------------------------------------------

def _mount(sensor: SensorSpec, default):
    return sensor.mount if sensor.mount is not None else default


def _lidar(sensor: SensorSpec, spec: RobotSpec, world: str):
    bx, by, bz = spec.body.size
    x, y, z = _mount(sensor, [bx / 2 - 0.03, 0, bz / 2 + 0.03])
    topic = sensor.topic or "/scan"
    xml = f'''
  <link name="lidar_link"/>
  <joint name="lidar_joint" type="fixed"><parent link="base_link"/><child link="lidar_link"/><origin xyz="{x} {y} {z}"/></joint>
  <gazebo reference="lidar_link">
    <sensor name="lidar" type="gpu_lidar">
      <topic>{topic.lstrip("/")}</topic><gz_frame_id>lidar_link</gz_frame_id>
      <update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>
      <lidar>
        <scan><horizontal><samples>180</samples><resolution>1</resolution><min_angle>-1.5708</min_angle><max_angle>1.5708</max_angle></horizontal></scan>
        <range><min>0.08</min><max>10.0</max><resolution>0.01</resolution></range>
      </lidar>
    </sensor>
  </gazebo>'''
    return {
        "xml": xml,
        "bridges": [Bridge(f"{topic}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan")],
        "world_systems": ["gz-sim-sensors-system"],
        "manifest_sensor": ("lidar", {"enabled": True, "topic": topic}),
        "ready_topics": [topic],
    }


def _imu(sensor: SensorSpec, spec: RobotSpec, world: str):
    bx, by, bz = spec.body.size
    x, y, z = _mount(sensor, [0, 0, bz / 2])
    topic = sensor.topic or "/imu"
    xml = f'''
  <link name="imu_link"/>
  <joint name="imu_joint" type="fixed"><parent link="base_link"/><child link="imu_link"/><origin xyz="{x} {y} {z}"/></joint>
  <gazebo reference="imu_link">
    <sensor name="imu" type="imu"><topic>{topic.lstrip("/")}</topic><gz_frame_id>imu_link</gz_frame_id><update_rate>50</update_rate><always_on>true</always_on></sensor>
  </gazebo>'''
    return {
        "xml": xml,
        "bridges": [Bridge(f"{topic}@sensor_msgs/msg/Imu[gz.msgs.IMU")],
        "world_systems": ["gz-sim-imu-system"],
        "manifest_sensor": ("imu", {"enabled": True, "topic": topic}),
        "ready_topics": [],
    }


def _contact(sensor: SensorSpec, spec: RobotSpec, world: str):
    # The base_link collision is lumped into base_footprint via the fixed base_joint; that is
    # the collision name sdformat produces, and the contact sensor must reference it. The
    # sensor also ignores its <topic>, publishing on the scoped gz path — so the bridge targets
    # that path and remaps it to /bumper. The compiler owns both of these gotchas.
    collision = "base_footprint_fixed_joint_lump__base_link_collision"
    topic = sensor.topic or "/bumper"
    scoped = f"/world/{world}/model/{spec.name}/link/base_footprint/sensor/bumper/contact"
    xml = f'''
  <gazebo reference="base_footprint">
    <sensor name="bumper" type="contact"><always_on>true</always_on><update_rate>30</update_rate>
      <contact><collision>{collision}</collision></contact>
    </sensor>
  </gazebo>'''
    return {
        "xml": xml,
        "bridges": [Bridge(f"{scoped}@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts",
                           remap=(scoped, topic))],
        "world_systems": ["gz-sim-contact-system"],
        "manifest_sensor": ("contact", {"enabled": True, "topic": topic}),
        "ready_topics": [],
    }


SENSORS = {"lidar": _lidar, "imu": _imu, "contact": _contact}


# ---- the compiler -----------------------------------------------------------

def compile_robot(spec: RobotSpec, world_name: str = "warehouse") -> CompiledRobot:
    if spec.base not in ARCHETYPES:
        raise UnknownArchetype(
            f"unknown base {spec.base!r}; known: {sorted(ARCHETYPES)} (or import via base: custom)")
    links, plugins, bridges, manifest, spawn_z = ARCHETYPES[spec.base](spec)

    sensor_xml = ""
    world_systems: list[str] = []
    manifest_sensors: dict = {}
    ready_topics = list(manifest["ready_topics"])
    for s in spec.sensors:
        if s.type not in SENSORS:
            raise UnknownSensor(f"unknown sensor {s.type!r}; known: {sorted(SENSORS)}")
        out = SENSORS[s.type](s, spec, world_name)
        sensor_xml += out["xml"]
        bridges += out["bridges"]
        for sys_ in out["world_systems"]:
            if sys_ not in world_systems:
                world_systems.append(sys_)
        key, val = out["manifest_sensor"]
        manifest_sensors[key] = val
        for t in out["ready_topics"]:
            if t not in ready_topics:
                ready_topics.append(t)

    urdf = (f'<?xml version="1.0"?>\n'
            f'<!-- Generated by Robotbase from robot.yaml — edit the spec, not this file. -->\n'
            f'<robot name="{spec.name}" xmlns:xacro="http://ros.org/wiki/xacro">\n'
            f'{links}\n{plugins}\n{sensor_xml}\n</robot>\n')

    full_manifest = {
        "robot": {"template": spec.base, "name": spec.name},
        "sensors": manifest_sensors,
        "control": manifest["control"],
        "ready_topics": ready_topics,
        "fixed_base": manifest["fixed_base"],
    }
    return CompiledRobot(name=spec.name, urdf=urdf, bridges=bridges,
                         world_systems=world_systems, manifest=full_manifest, spawn_z=spawn_z)
