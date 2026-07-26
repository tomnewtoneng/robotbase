"""Sensor emitters — cross-archetype; each mounts to any link (see declarative-compiler.md)."""
from __future__ import annotations

from dataclasses import dataclass

from robotbase.robotspec.ir import Bridge, Fragment, LinkIR
from robotbase.robotspec.merge import fixed_joint


class UnknownSensor(ValueError):
    ...


@dataclass
class Ctx:
    world: str
    robot_name: str
    body_size: list[float]
    base_link: str = "base_link"


def _mount(params, on_link, ctx, base_default):
    m = params.get("mount")
    if m is not None:
        return m
    return base_default if on_link == ctx.base_link else [0, 0, 0]


def _lidar(params, on_link, ctx) -> Fragment:
    bx, by, bz = ctx.body_size
    x, y, z = _mount(params, on_link, ctx, [bx/2 - 0.03, 0, bz/2 + 0.03])
    topic = params.get("topic") or "/scan"
    f = Fragment(world_systems=["gz-sim-sensors-system"], ready_topics=[topic])
    f.links.append(LinkIR("lidar_link", '\n  <link name="lidar_link"/>'))
    f.joints.append(fixed_joint("lidar_joint", on_link, "lidar_link", xyz=f"{x} {y} {z}"))
    f.gazebo.append(
        f'\n  <gazebo reference="lidar_link"><sensor name="lidar" type="gpu_lidar">'
        f'<topic>{topic.lstrip("/")}</topic><gz_frame_id>lidar_link</gz_frame_id>'
        '<update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>'
        '<lidar><scan><horizontal><samples>180</samples><resolution>1</resolution>'
        '<min_angle>-1.5708</min_angle><max_angle>1.5708</max_angle></horizontal></scan>'
        '<range><min>0.08</min><max>10.0</max><resolution>0.01</resolution></range></lidar></sensor></gazebo>')
    f.bridges.append(Bridge(f"{topic}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan"))
    f.manifest_sensors["lidar"] = {"enabled": True, "topic": topic}
    return f


def _imu(params, on_link, ctx) -> Fragment:
    bx, by, bz = ctx.body_size
    x, y, z = _mount(params, on_link, ctx, [0, 0, bz/2])
    topic = params.get("topic") or "/imu"
    f = Fragment(world_systems=["gz-sim-imu-system"])
    f.links.append(LinkIR("imu_link", '\n  <link name="imu_link"/>'))
    f.joints.append(fixed_joint("imu_joint", on_link, "imu_link", xyz=f"{x} {y} {z}"))
    f.gazebo.append(
        f'\n  <gazebo reference="imu_link"><sensor name="imu" type="imu">'
        f'<topic>{topic.lstrip("/")}</topic><gz_frame_id>imu_link</gz_frame_id>'
        '<update_rate>50</update_rate><always_on>true</always_on></sensor></gazebo>')
    f.bridges.append(Bridge(f"{topic}@sensor_msgs/msg/Imu[gz.msgs.IMU"))
    f.manifest_sensors["imu"] = {"enabled": True, "topic": topic}
    return f


def _contact(params, on_link, ctx) -> Fragment:
    # Documented limit: contact stays on base_footprint (collision-lump naming is base-specific).
    collision = "base_footprint_fixed_joint_lump__base_link_collision"
    topic = params.get("topic") or "/bumper"
    scoped = f"/world/{ctx.world}/model/{ctx.robot_name}/link/base_footprint/sensor/bumper/contact"
    f = Fragment(world_systems=["gz-sim-contact-system"])
    f.gazebo.append(
        f'\n  <gazebo reference="base_footprint"><sensor name="bumper" type="contact">'
        '<always_on>true</always_on><update_rate>30</update_rate>'
        f'<contact><collision>{collision}</collision></contact></sensor></gazebo>')
    f.bridges.append(Bridge(f"{scoped}@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts",
                            remap=(scoped, topic)))
    f.manifest_sensors["contact"] = {"enabled": True, "topic": topic}
    return f


SENSORS = {"lidar": _lidar, "imu": _imu, "contact": _contact}
