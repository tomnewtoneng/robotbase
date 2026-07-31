"""The typed, backend-neutral semantic IR (P4 — see docs/design/declarative-compiler.md).

Robotbase compiles a robot spec into semantic concepts — Geometry, Inertial, RigidBody, Joint,
Sensor, RobotModel — and the backends in ``backends/`` render those to URDF/SDF/MJCF. This module
is *pure data + the geometry/inertia math*; it produces no XML. It owns the inertia formulas that
used to live inside ``ir.link_from_shape`` so there is exactly one source of truth for them.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class RigidBody:
    """A link: a named body with an optional geometry (None = a massless frame link, e.g.
    ``base_footprint``/``world``). ``geometry`` is a typed Geometry or a ``(shape, size)`` tuple.

    The inertia is auto-computed from geometry + mass unless an explicit ``inertia`` is given (the
    archetype links carry hand-tuned tensors). ``*_origin`` are the inner attributes of an
    ``<origin/>`` element on the inertial/collision/visual sub-element (e.g. ``'rpy="1.5708 0 0"'``
    or ``'xyz="0 0 0.2"'``) — kept as strings so the backend stays free of pose math. ``friction`` is
    an ODE ``(mu, mu2)`` surface on the collision; ``has_collision=False`` is a visual-only body (a
    rotor); ``material=None`` omits the visual ``<material>``. Everything numeric renders through the
    one formatter, so the IR is backend-neutral and a second backend can read real numbers."""
    name: str
    geometry: "Geometry | tuple[str, list[float]] | None" = None
    mass: float = 0.0
    inertia: "Inertial | None" = None
    inertial_origin: str | None = None
    collision_origin: str | None = None
    visual_origin: str | None = None
    friction: tuple[float, float] | None = None
    has_collision: bool = True
    material: str | None = "grey"
    rgba: str = "0.4 0.4 0.45 1"
    raw_xml: str | None = None  # explicit escape hatch: a user's verbatim <link> from a raw part
    # (portability-breaking by design — a non-URDF backend cannot render it).


@dataclass(frozen=True)
class Joint:
    """A joint between two links. ``xyz``/``rpy``/``axis`` are backend-agnostic strings so a migrated
    module reproduces its exact placement bytes; ``rpy=None`` renders an xyz-only origin (the module
    form) while a set ``rpy`` renders both (the ``fixed_joint`` form). ``limit`` is the
    ``(lower, upper, effort, velocity)`` attribute strings, present only for revolute/prismatic."""
    name: str
    type: str
    parent: str
    child: str
    xyz: str = "0 0 0"
    rpy: str | None = None
    axis: str | None = None
    limit: tuple[str, str, str, str] | None = None


@dataclass(frozen=True)
class Sensor:
    """A sensor to mount on the robot. The backend renders its frame link (``link_name``), its fixed
    mounting joint (``mount_link`` + ``xyz``), and the gz ``<sensor>`` block (keyed by ``gz_type``).
    ``reference`` is the ``<gazebo reference="..">``/``gz_frame_id`` link (the sensor link, or
    ``base_footprint`` for a chassis contact sensor). ``resolution`` is camera/depth ``(w, h)``;
    ``collision`` is the contact sensor's collision element. Bridges/world-systems/manifest entries
    stay with the emitter — they are wiring, not geometry."""
    kind: str
    name: str
    gz_type: str
    reference: str
    topic: str
    mount_link: str | None = None
    xyz: str | None = None
    link_name: str | None = None
    resolution: tuple[int, int] | None = None
    collision: str | None = None


class InvalidAssembly(ValueError):
    """A robot's link/joint tree is malformed (dupes, missing/orphan links, cycles)."""


@dataclass
class RobotModel:
    """The whole robot as typed parts: bodies + joints + the gz blocks (plugins/sensor blocks/per-ref
    tweaks, still pre-rendered strings for now) that the URDF backend assembles into one ``<robot>``.
    The remaining fields are the compiler's manifest outputs (control/ready_topics/bridges/…), carried
    here so ``compile_robot`` can build one object instead of a tuple."""
    name: str
    root: str
    bodies: list[RigidBody] = field(default_factory=list)
    joints: list[Joint] = field(default_factory=list)
    gazebo: list[str] = field(default_factory=list)
    bridges: list = field(default_factory=list)
    world_systems: list[str] = field(default_factory=list)
    ready_topics: list[str] = field(default_factory=list)
    control: dict | None = None
    fixed_base: bool | None = None
    manifest_sensors: dict = field(default_factory=dict)


def validate_tree(model: RobotModel) -> None:
    """Validate the link/joint tree on typed bodies/joints (the old merge._validate, same errors):
    no duplicate link/joint names, every joint's parent/child exists, one parent per link, and every
    non-root link reaches the root without a cycle."""
    names = [b.name for b in model.bodies]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        raise InvalidAssembly(f"duplicate link name(s): {sorted(dupes)}")
    jnames = [j.name for j in model.joints]
    jdupes = {n for n in jnames if jnames.count(n) > 1}
    if jdupes:
        raise InvalidAssembly(f"duplicate joint name(s): {sorted(jdupes)}")
    linkset = set(names)
    if model.root not in linkset:
        raise InvalidAssembly(f"root link {model.root!r} not present")
    child_of = {}
    for j in model.joints:
        if j.parent not in linkset:
            raise InvalidAssembly(f"joint {j.name!r} references missing parent link {j.parent!r}")
        if j.child not in linkset:
            raise InvalidAssembly(f"joint {j.name!r} references missing child link {j.child!r}")
        if j.child in child_of:
            raise InvalidAssembly(f"link {j.child!r} has two parent joints")
        child_of[j.child] = j.parent
    if model.root in child_of:
        raise InvalidAssembly(
            f"root link {model.root!r} must not be a child of any joint (cycle through root)")
    for n in linkset:
        if n == model.root:
            continue
        seen, cur = set(), n
        while cur != model.root:
            if cur not in child_of:
                raise InvalidAssembly(f"link {n!r} is not connected to root {model.root!r} (orphan)")
            if cur in seen:
                raise InvalidAssembly(f"cycle detected at link {cur!r}")
            seen.add(cur)
            cur = child_of[cur]
