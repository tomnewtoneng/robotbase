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
    geometry_from_spec,
    inertial_for,
)


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
