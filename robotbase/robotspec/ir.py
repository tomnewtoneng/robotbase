"""The primitive IR every compilation target emits into (see docs/design/declarative-compiler.md).

Modules (archetypes) and sensors contribute Fragments; the compiler merges them, validates the
link tree, and renders URDF once. LinkIR/JointIR carry already-rendered XML; link_from_shape
turns a {shape,size,mass} primitive into a full <link> with an auto-computed inertia tensor so
hand-authored parts are not finicky.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Bridge:
    arg: str                                  # a parameter_bridge argument
    remap: tuple[str, str] | None = None      # (from, to) when the gz topic != the ROS topic


@dataclass
class LinkIR:
    name: str
    xml: str                                  # full <link>…</link>


@dataclass
class JointIR:
    name: str
    xml: str                                  # full <joint>…</joint>


@dataclass
class Fragment:
    links: list[LinkIR] = field(default_factory=list)
    joints: list[JointIR] = field(default_factory=list)
    gazebo: list[str] = field(default_factory=list)          # <gazebo> blocks (plugins/sensors/per-ref)
    bridges: list[Bridge] = field(default_factory=list)
    world_systems: list[str] = field(default_factory=list)
    ready_topics: list[str] = field(default_factory=list)
    exposes: list[str] = field(default_factory=list)         # link names offered as mount points
    control: dict | None = None                              # set by the module owning locomotion
    fixed_base: bool | None = None
    manifest_sensors: dict = field(default_factory=dict)


class UnknownShape(ValueError):
    ...


def _fmt(v: float) -> str:
    # trim trailing zeros so 0.025 not 0.025000000001; keep ints clean
    return f"{round(v, 9):g}"


def link_from_shape(name, shape, size, mass, material="grey", rgba="0.4 0.4 0.45 1") -> LinkIR:
    if shape == "box":
        x, y, z = size
        ixx, iyy, izz = mass * (y*y + z*z) / 12, mass * (x*x + z*z) / 12, mass * (x*x + y*y) / 12
        geom = f'<box size="{_fmt(x)} {_fmt(y)} {_fmt(z)}"/>'
    elif shape == "cylinder":
        r, h = size
        ixx = iyy = mass * (3*r*r + h*h) / 12
        izz = mass * r*r / 2
        geom = f'<cylinder radius="{_fmt(r)}" length="{_fmt(h)}"/>'
    elif shape == "sphere":
        r = size[0]
        ixx = iyy = izz = 2 * mass * r*r / 5
        geom = f'<sphere radius="{_fmt(r)}"/>'
    else:
        raise UnknownShape(f"unknown shape {shape!r}; known: box, cylinder, sphere")
    xml = (f'\n  <link name="{name}">'
           f'\n    <inertial><mass value="{_fmt(mass)}"/>'
           f'<inertia ixx="{_fmt(ixx)}" ixy="0" ixz="0" iyy="{_fmt(iyy)}" iyz="0" izz="{_fmt(izz)}"/></inertial>'
           f'\n    <collision><geometry>{geom}</geometry></collision>'
           f'\n    <visual><geometry>{geom}</geometry><material name="{material}"><color rgba="{rgba}"/></material></visual>'
           f'\n  </link>')
    return LinkIR(name, xml)
