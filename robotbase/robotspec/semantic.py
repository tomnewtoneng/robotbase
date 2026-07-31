"""The typed, backend-neutral semantic IR (P4 — see docs/design/declarative-compiler.md).

Robotbase compiles a robot spec into semantic concepts — Geometry, Inertial, RigidBody, Joint,
Sensor, RobotModel — and the backends in ``backends/`` render those to URDF/SDF/MJCF. This module
is *pure data + the geometry/inertia math*; it produces no XML. It owns the inertia formulas that
used to live inside ``ir.link_from_shape`` so there is exactly one source of truth for them.
"""
from __future__ import annotations

from dataclasses import dataclass

from robotbase.robotspec.ir import SHAPE_SIZE, ShapeSizeError, UnknownShape


@dataclass(frozen=True)
class Box:
    size: list[float]
    kind: str = "box"


@dataclass(frozen=True)
class Cylinder:
    radius: float
    length: float
    kind: str = "cylinder"


@dataclass(frozen=True)
class Sphere:
    radius: float
    kind: str = "sphere"


Geometry = Box | Cylinder | Sphere


@dataclass(frozen=True)
class Inertial:
    mass: float
    ixx: float
    iyy: float
    izz: float


def geometry_from_spec(shape: str, size) -> Geometry:
    """Build a typed Geometry from a {shape, size} primitive, validating size length against the
    one SHAPE_SIZE rule (same UnknownShape/ShapeSizeError as ir.link_from_shape)."""
    if shape not in SHAPE_SIZE:
        raise UnknownShape(f"unknown shape {shape!r}; known: box, cylinder, sphere")
    need, fmt = SHAPE_SIZE[shape]
    size = list(size)
    if len(size) != need:
        raise ShapeSizeError(
            f"{shape} size must be {fmt} ({need} value{'s' if need > 1 else ''}), "
            f"got {len(size)}: {size}")
    if shape == "box":
        return Box(size)
    if shape == "cylinder":
        return Cylinder(size[0], size[1])
    return Sphere(size[0])


def inertial_for(g: Geometry, mass: float) -> Inertial:
    """The auto-computed inertia tensor for a geometry — the exact formulas from ir.link_from_shape."""
    if isinstance(g, Box):
        x, y, z = g.size
        return Inertial(mass, mass*(y*y + z*z)/12, mass*(x*x + z*z)/12, mass*(x*x + y*y)/12)
    if isinstance(g, Cylinder):
        r, h = g.radius, g.length
        i = mass * (3*r*r + h*h) / 12
        return Inertial(mass, i, i, mass * r*r / 2)
    r = g.radius
    i = 2 * mass * r*r / 5
    return Inertial(mass, i, i, i)
