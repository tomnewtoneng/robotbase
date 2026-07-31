"""Sensor emitters — cross-archetype; each mounts to any link (see declarative-compiler.md)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from robotbase.robotspec.ir import Bridge, Fragment, JointIR, LinkIR
from robotbase.robotspec.semantic import Sensor
from robotbase.robotspec.backends.urdf import render_sensor


class UnknownSensor(ValueError):
    ...


# Map a Gazebo <sensor type="..."> to the robotbase sensor name, so an imported URDF's own
# sensors can be recognised (to wire their bridge/world-system without re-injecting their XML).
_GZ_SENSOR_MAP = {"gpu_lidar": "lidar", "lidar": "lidar", "imu": "imu",
                  "contact": "contact", "camera": "camera", "depth_camera": "depth"}


def infer_sensors_from_urdf(urdf_text: str) -> list[str]:
    """Best-effort: the robotbase sensor types already present in an imported URDF."""
    seen: list[str] = []
    for gz_type in re.findall(r'<sensor\b[^>]*\btype="([^"]+)"', urdf_text):
        rb = _GZ_SENSOR_MAP.get(gz_type)
        if rb and rb not in seen:
            seen.append(rb)
    return seen


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


def _emit(f: Fragment, s: Sensor) -> None:
    """Render a Sensor through the URDF backend and attach its link/joint/gazebo to the fragment.
    A contact sensor has no frame link/joint (it sits on an existing chassis link)."""
    link_xml, joint_xml, gazebo_xml = render_sensor(s)
    if link_xml:
        f.links.append(LinkIR(s.link_name, link_xml))
    if joint_xml:
        f.joints.append(JointIR(f"{s.kind}_joint", joint_xml, parent=s.mount_link, child=s.link_name))
    f.gazebo.append(gazebo_xml)


def _lidar(params, on_link, ctx) -> Fragment:
    bx, by, bz = ctx.body_size
    x, y, z = _mount(params, on_link, ctx, [bx/2 - 0.03, 0, bz/2 + 0.03])
    topic = params.get("topic") or "/scan"
    f = Fragment(world_systems=["gz-sim-sensors-system"], ready_topics=[topic])
    _emit(f, Sensor(kind="lidar", name="lidar", gz_type="gpu_lidar", reference="lidar_link",
                    topic=topic, mount_link=on_link, xyz=f"{x} {y} {z}", link_name="lidar_link"))
    f.bridges.append(Bridge(f"{topic}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan"))
    f.manifest_sensors["lidar"] = {"enabled": True, "topic": topic}
    return f


def _imu(params, on_link, ctx) -> Fragment:
    bx, by, bz = ctx.body_size
    x, y, z = _mount(params, on_link, ctx, [0, 0, bz/2])
    topic = params.get("topic") or "/imu"
    f = Fragment(world_systems=["gz-sim-imu-system"])
    _emit(f, Sensor(kind="imu", name="imu", gz_type="imu", reference="imu_link",
                    topic=topic, mount_link=on_link, xyz=f"{x} {y} {z}", link_name="imu_link"))
    f.bridges.append(Bridge(f"{topic}@sensor_msgs/msg/Imu[gz.msgs.IMU"))
    f.manifest_sensors["imu"] = {"enabled": True, "topic": topic}
    return f


def _camera(params, on_link, ctx) -> Fragment:
    bx, by, bz = ctx.body_size
    x, y, z = _mount(params, on_link, ctx, [bx / 2, 0, bz / 2])
    topic = params.get("topic") or "/image"
    w, h = params.get("resolution") or [320, 240]
    f = Fragment(world_systems=["gz-sim-sensors-system"])
    _emit(f, Sensor(kind="camera", name="camera", gz_type="camera", reference="camera_link",
                    topic=topic, mount_link=on_link, xyz=f"{x} {y} {z}", link_name="camera_link",
                    resolution=(w, h)))
    f.bridges.append(Bridge(f"{topic}@sensor_msgs/msg/Image[gz.msgs.Image"))
    f.manifest_sensors["camera"] = {"enabled": True, "topic": topic}
    return f


def _depth(params, on_link, ctx) -> Fragment:
    bx, by, bz = ctx.body_size
    x, y, z = _mount(params, on_link, ctx, [bx / 2, 0, bz / 2])
    topic = params.get("topic") or "/depth"
    w, h = params.get("resolution") or [320, 240]
    f = Fragment(world_systems=["gz-sim-sensors-system"])
    _emit(f, Sensor(kind="depth", name="depth", gz_type="depth_camera", reference="depth_link",
                    topic=topic, mount_link=on_link, xyz=f"{x} {y} {z}", link_name="depth_link",
                    resolution=(w, h)))
    f.bridges.append(Bridge(f"{topic}@sensor_msgs/msg/Image[gz.msgs.Image"))
    f.bridges.append(Bridge(f"{topic}/points@sensor_msgs/msg/PointCloud2[gz.msgs.PointCloudPacked"))
    f.manifest_sensors["depth"] = {"enabled": True, "topic": topic}
    return f


def _contact(params, on_link, ctx) -> Fragment:
    # Documented limit: contact stays on base_footprint (collision-lump naming is base-specific).
    collision = "base_footprint_fixed_joint_lump__base_link_collision"
    topic = params.get("topic") or "/bumper"
    scoped = f"/world/{ctx.world}/model/{ctx.robot_name}/link/base_footprint/sensor/bumper/contact"
    f = Fragment(world_systems=["gz-sim-contact-system"])
    _emit(f, Sensor(kind="contact", name="bumper", gz_type="contact", reference="base_footprint",
                    topic=topic, collision=collision))
    f.bridges.append(Bridge(f"{scoped}@ros_gz_interfaces/msg/Contacts[gz.msgs.Contacts",
                            remap=(scoped, topic)))
    f.manifest_sensors["contact"] = {"enabled": True, "topic": topic}
    return f


SENSORS = {"lidar": _lidar, "imu": _imu, "camera": _camera, "depth": _depth, "contact": _contact}
