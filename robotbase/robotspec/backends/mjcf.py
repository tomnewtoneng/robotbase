"""The MJCF (MuJoCo) backend — the payoff of the semantic IR (P4).

This exists to prove one thing: a second robot-description backend is an *additive file* over the
same ``RobotModel``, not a rewrite. It reads the identical typed bodies/joints that ``urdf.py``
renders — real numeric geometry and inertia — and emits MuJoCo XML, with ZERO changes to the IR or
the emitters. That directly kills the vision's #1 kill-signal: "the IR is coupled to Gazebo/URDF."

Scope is the common subset — a ``<body>`` per RigidBody with its geometry, and a hinge ``<joint>``
for revolute/continuous joints (fixed joints fold into the body pose). It is intentionally NOT full
parity: no gz plugins/sensors (URDF-<gazebo> is Gazebo-specific), no kinematic-tree nesting, no
actuators. Those are future work; the point here is the seam, not completeness.
"""
from __future__ import annotations

from robotbase.robotspec.ir import _fmt
from robotbase.robotspec.semantic import Box, Cylinder, Sphere, RigidBody, RobotModel, geometry_from_spec


def _geom(b: RigidBody) -> str:
    """A MuJoCo <geom> from the body's typed geometry (MJCF uses half-extents / half-length)."""
    g = b.geometry
    if not isinstance(g, (Box, Cylinder, Sphere)):
        g = geometry_from_spec(*g)
    if isinstance(g, Box):
        x, y, z = g.size
        return f'<geom type="box" size="{_fmt(x/2)} {_fmt(y/2)} {_fmt(z/2)}"/>'
    if isinstance(g, Cylinder):
        return f'<geom type="cylinder" size="{_fmt(g.radius)} {_fmt(g.length/2)}"/>'
    return f'<geom type="sphere" size="{_fmt(g.radius)}"/>'


def render_mjcf(model: RobotModel) -> str:
    """Render a RobotModel to a minimal MuJoCo model — one <body> per RigidBody (a hinge <joint> for
    revolute/continuous joints; fixed joints just position the body). Frame links (no geometry) and
    raw-XML escape-hatch links become empty bodies; gz plugins/sensors are out of scope."""
    joint_by_child = {j.child: j for j in model.joints}
    bodies = []
    for b in model.bodies:
        j = joint_by_child.get(b.name)
        pos = j.xyz if j is not None else "0 0 0"
        parts = [f'\n    <body name="{b.name}" pos="{pos}">']
        if j is not None and j.type in ("revolute", "continuous"):
            axis = j.axis or "0 0 1"
            parts.append(f'<joint name="{j.name}" type="hinge" axis="{axis}"/>')
        if b.geometry is not None and b.raw_xml is None:
            parts.append(_geom(b))
        parts.append("</body>")
        bodies.append("".join(parts))
    return (f'<mujoco model="{model.name}">'
            f'\n  <worldbody>{"".join(bodies)}'
            f'\n  </worldbody>\n</mujoco>\n')
