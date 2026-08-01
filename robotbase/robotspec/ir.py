"""Cross-cutting primitives the compiler emits into (see docs/design/declarative-compiler.md).

Modules (archetypes) and sensors contribute Fragments of typed semantic parts — RigidBody/Joint
from ``robotbase.robotspec.semantic`` — which the compiler merges into a RobotModel that the
backends render. This module holds the pieces that don't belong to a single stage: the Bridge and
Fragment carriers, the one shape->size rule (SHAPE_SIZE, shared by the schemas and the backend),
the ``body_xyz`` placement helper, and the ``_fmt`` number formatter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robotbase.robotspec.semantic import Joint, RigidBody


@dataclass
class Bridge:
    arg: str                                  # a parameter_bridge argument
    remap: tuple[str, str] | None = None      # (from, to) when the gz topic != the ROS topic


@dataclass
class Fragment:
    links: list[RigidBody] = field(default_factory=list)
    joints: list[Joint] = field(default_factory=list)
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
