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
    parent: str = ""
    child: str = ""


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


class ShapeSizeError(ValueError):
    """A shape's `size` had the wrong number of values (would otherwise crash the URDF renderer)."""


# The one place shape -> size-length is defined; schema validators import this so the docs, the
# schema, and the renderer can never disagree about what `size` means for each shape.
SHAPE_SIZE = {"box": (3, "[x, y, z]"), "cylinder": (2, "[radius, length]"), "sphere": (1, "[radius]")}


def body_xyz(size, shape: str = "box") -> list[float]:
    """A 3-value bounding box [x, y, z] for any body shape, used for placement math (wheels,
    default sensor mounts). Keeps a cylinder/sphere body from crashing code that needs x,y,z."""
    size = list(size)
    if shape == "cylinder" and len(size) == 2:
        r, h = size
        return [2 * r, 2 * r, h]
    if shape == "sphere" and len(size) == 1:
        r = size[0]
        return [2 * r, 2 * r, 2 * r]
    if len(size) == 3:
        return size
    return [0.35, 0.30, 0.15]


def _fmt(v: float) -> str:
    # trim trailing zeros so 0.025 not 0.025000000001; keep ints clean
    return f"{round(v, 9):g}"


def link_from_shape(name, shape, size, mass, material="grey", rgba="0.4 0.4 0.45 1") -> LinkIR:
    """Turn a {shape, size, mass} primitive into a full <link> with an auto-computed inertia tensor.

    A thin adapter over the semantic IR: it builds a RigidBody and renders it through the one URDF
    backend, so there is a single renderer. The geometry/size validation (UnknownShape/ShapeSizeError)
    now lives in semantic.geometry_from_spec. (Local imports avoid an ir -> backends -> semantic -> ir
    import cycle.)"""
    from robotbase.robotspec.semantic import RigidBody
    from robotbase.robotspec.backends.urdf import render_body
    return LinkIR(name, render_body(RigidBody(name, (shape, size), mass, material, rgba)))
