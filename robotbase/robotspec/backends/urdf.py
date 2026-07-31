"""The URDF backend — the ONLY place URDF strings are produced (P4).

``render_body``/``render_joint`` reproduce, byte-for-byte, the XML the legacy ``ir.link_from_shape``
and ``merge.fixed_joint`` (and the module joint templates) emitted, so the migration is a refactor,
not a behaviour change (guarded by ``tests/test_golden_output.py``). ``render_urdf`` (Task 6)
assembles the whole ``<robot>`` from a ``RobotModel``.
"""
from __future__ import annotations

from robotbase.robotspec.ir import _fmt
from robotbase.robotspec.semantic import (
    Box,
    Cylinder,
    Sphere,
    Geometry,
    RigidBody,
    Joint,
    Sensor,
    geometry_from_spec,
    inertial_for,
)


class UnknownGzSensor(ValueError):
    ...


def _geom_xml(g: Geometry) -> str:
    """The `<box|cylinder|sphere .../>` element — identical to ir.link_from_shape's geom strings."""
    if isinstance(g, Box):
        x, y, z = g.size
        return f'<box size="{_fmt(x)} {_fmt(y)} {_fmt(z)}"/>'
    if isinstance(g, Cylinder):
        return f'<cylinder radius="{_fmt(g.radius)}" length="{_fmt(g.length)}"/>'
    return f'<sphere radius="{_fmt(g.radius)}"/>'


def render_body(b: RigidBody) -> str:
    """Render a link. A ``None`` geometry is a massless frame link (``<link name=".."/>``);
    otherwise the inertia is auto-computed from the geometry + mass exactly as before."""
    if b.geometry is None:
        return f'\n  <link name="{b.name}"/>'
    g = b.geometry if isinstance(b.geometry, (Box, Cylinder, Sphere)) else geometry_from_spec(*b.geometry)
    inr = inertial_for(g, b.mass)
    geom = _geom_xml(g)
    return (f'\n  <link name="{b.name}">'
            f'\n    <inertial><mass value="{_fmt(b.mass)}"/>'
            f'<inertia ixx="{_fmt(inr.ixx)}" ixy="0" ixz="0" iyy="{_fmt(inr.iyy)}" iyz="0" izz="{_fmt(inr.izz)}"/></inertial>'
            f'\n    <collision><geometry>{geom}</geometry></collision>'
            f'\n    <visual><geometry>{geom}</geometry><material name="{b.material}"><color rgba="{b.rgba}"/></material></visual>'
            f'\n  </link>')


def render_joint(j: Joint) -> str:
    """Render a joint. ``rpy=None`` gives an xyz-only origin (module form); a set ``rpy`` gives the
    two-attribute origin (``fixed_joint`` form). ``axis``/``limit`` are appended when present."""
    origin = f'<origin xyz="{j.xyz}"' + (f' rpy="{j.rpy}"' if j.rpy is not None else "") + "/>"
    axis = f'<axis xyz="{j.axis}"/>' if j.axis is not None else ""
    limit = ""
    if j.limit is not None:
        lo, hi, eff, vel = j.limit
        limit = f'<limit lower="{lo}" upper="{hi}" effort="{eff}" velocity="{vel}"/>'
    return (f'\n  <joint name="{j.name}" type="{j.type}">'
            f'<parent link="{j.parent}"/><child link="{j.child}"/>'
            f'{origin}{axis}{limit}</joint>')


def _sensor_gazebo(s: Sensor) -> str:
    """The gz `<gazebo reference=..><sensor ..>..</sensor></gazebo>` block, keyed by gz_type."""
    gt = s.topic.lstrip("/")
    ref = s.reference
    head = f'\n  <gazebo reference="{ref}"><sensor name="{s.name}" type="{s.gz_type}">'
    if s.gz_type == "gpu_lidar":
        return (head
                + f'<topic>{gt}</topic><gz_frame_id>{ref}</gz_frame_id>'
                + '<update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>'
                + '<lidar><scan><horizontal><samples>180</samples><resolution>1</resolution>'
                + '<min_angle>-1.5708</min_angle><max_angle>1.5708</max_angle></horizontal></scan>'
                + '<range><min>0.08</min><max>10.0</max><resolution>0.01</resolution></range></lidar></sensor></gazebo>')
    if s.gz_type == "imu":
        return (head
                + f'<topic>{gt}</topic><gz_frame_id>{ref}</gz_frame_id>'
                + '<update_rate>50</update_rate><always_on>true</always_on></sensor></gazebo>')
    if s.gz_type == "camera":
        w, h = s.resolution
        return (head
                + f'<topic>{gt}</topic><gz_frame_id>{ref}</gz_frame_id>'
                + '<update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>'
                + '<camera><horizontal_fov>1.047</horizontal_fov>'
                + f'<image><width>{w}</width><height>{h}</height><format>R8G8B8</format></image>'
                + '<clip><near>0.1</near><far>100</far></clip></camera></sensor></gazebo>')
    if s.gz_type == "depth_camera":
        w, h = s.resolution
        return (head
                + f'<topic>{gt}</topic><gz_frame_id>{ref}</gz_frame_id>'
                + '<update_rate>10</update_rate><always_on>true</always_on><visualize>false</visualize>'
                + '<camera><horizontal_fov>1.047</horizontal_fov>'
                + f'<image><width>{w}</width><height>{h}</height></image>'
                + '<clip><near>0.1</near><far>10.0</far></clip></camera></sensor></gazebo>')
    if s.gz_type == "contact":
        return (head
                + '<always_on>true</always_on><update_rate>30</update_rate>'
                + f'<contact><collision>{s.collision}</collision></contact></sensor></gazebo>')
    raise UnknownGzSensor(f"no URDF rendering for gz sensor type {s.gz_type!r}")


def render_sensor(s: Sensor) -> tuple[str, str, str]:
    """Render a sensor to (link_xml, joint_xml, gazebo_xml). A contact sensor sits on an existing
    chassis link, so it has no frame link/joint (both empty). Everything else gets a massless frame
    link and a fixed mounting joint (rpy always present — matching the old merge.fixed_joint)."""
    link_xml = render_body(RigidBody(s.link_name)) if s.link_name else ""
    joint_xml = ""
    if s.mount_link is not None:
        joint_xml = render_joint(
            Joint(f"{s.kind}_joint", "fixed", s.mount_link, s.link_name, xyz=s.xyz, rpy="0 0 0"))
    return link_xml, joint_xml, _sensor_gazebo(s)
