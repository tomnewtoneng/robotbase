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
    RobotModel,
    geometry_from_spec,
    inertial_for,
    validate_tree,
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
    """Render a link. A ``None`` geometry is a massless frame link (``<link name=".."/>``). Otherwise
    the inertia is the explicit ``b.inertia`` or auto-computed from geometry + mass; per-element
    origins, an ODE friction surface, a visual-only body, and an omitted material are all supported so
    the archetype links render from typed fields. A plain shape (no overrides) renders exactly as the
    legacy link_from_shape did."""
    if b.raw_xml is not None:
        return b.raw_xml
    if b.geometry is None:
        return f'\n  <link name="{b.name}"/>'
    g = b.geometry if isinstance(b.geometry, (Box, Cylinder, Sphere)) else geometry_from_spec(*b.geometry)
    inr = b.inertia if b.inertia is not None else inertial_for(g, b.mass)
    geom = _geom_xml(g)
    io = f'<origin {b.inertial_origin}/>' if b.inertial_origin else ""
    inertial = (f'<inertial>{io}<mass value="{_fmt(inr.mass)}"/>'
                f'<inertia ixx="{_fmt(inr.ixx)}" ixy="0" ixz="0" iyy="{_fmt(inr.iyy)}" iyz="0" izz="{_fmt(inr.izz)}"/></inertial>')
    out = [f'\n  <link name="{b.name}">', f'\n    {inertial}']
    if b.has_collision:
        co = f'<origin {b.collision_origin}/>' if b.collision_origin else ""
        surface = ""
        if b.friction is not None:
            mu, mu2 = b.friction
            surface = f'<surface><friction><ode><mu>{_fmt(mu)}</mu><mu2>{_fmt(mu2)}</mu2></ode></friction></surface>'
        out.append(f'\n    <collision>{co}<geometry>{geom}</geometry>{surface}</collision>')
    vo = f'<origin {b.visual_origin}/>' if b.visual_origin else ""
    mat = f'<material name="{b.material}"><color rgba="{b.rgba}"/></material>' if b.material else ""
    out.append(f'\n    <visual>{vo}<geometry>{geom}</geometry>{mat}</visual>')
    out.append("\n  </link>")
    return "".join(out)


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


def sensor_parts(s: Sensor) -> tuple[RigidBody | None, Joint | None, str]:
    """A sensor as typed parts: its frame link (RigidBody), its fixed mounting joint (Joint), and the
    gz ``<sensor>`` block (still a string — plugin/sensor gz XML stays pre-rendered for now). A
    contact sensor sits on an existing chassis link, so it has no frame link/joint (both None). The
    mounting joint carries rpy="0 0 0" to match the old merge.fixed_joint form."""
    body = RigidBody(s.link_name) if s.link_name else None
    joint = None
    if s.mount_link is not None:
        joint = Joint(f"{s.kind}_joint", "fixed", s.mount_link, s.link_name, xyz=s.xyz, rpy="0 0 0")
    return body, joint, _sensor_gazebo(s)


def render_urdf(model: RobotModel) -> str:
    """Assemble the whole <robot>: header + every body + every joint + the gz blocks + footer —
    the semantic replacement for merge.merge_and_render's string concatenation. Validates the
    link/joint tree first (same errors as before)."""
    validate_tree(model)
    return (f'<?xml version="1.0"?>\n'
            f'<!-- Generated by Robotbase from robot.yaml — edit the spec, not this file. -->\n'
            f'<robot name="{model.name}" xmlns:xacro="http://ros.org/wiki/xacro">'
            + "".join(render_body(b) for b in model.bodies)
            + "".join(render_joint(j) for j in model.joints)
            + "".join(model.gazebo)
            + "\n</robot>\n")
