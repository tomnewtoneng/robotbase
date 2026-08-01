"""The typed world IR (P4) — mirrors robotspec.semantic for the world side.

A WorldSpec compiles into a WorldModel of typed parts (static models, lights, systems, includes);
the SDF backend renders it. Pure data, no XML.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Box:
    size: list[float]              # [x, y, z]
    kind: str = "box"


@dataclass(frozen=True)
class Cylinder:
    radius: float
    length: float
    kind: str = "cylinder"


@dataclass(frozen=True)
class Plane:
    normal: str = "0 0 1"
    size: str = "100 100"
    kind: str = "plane"


WGeometry = Box | Cylinder | Plane


@dataclass
class StaticModel:
    """A static world model — obstacle, wall, ground, or goal. ``has_collision=False`` +
    ``material`` (a verbatim SDF ``<material>`` string) is the goal-marker form; everything else is a
    collidable body with no material override."""
    name: str
    geometry: WGeometry
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0
    has_collision: bool = True
    material: str | None = None


@dataclass
class WorldModel:
    name: str
    systems: list[str] = field(default_factory=list)   # gz system filenames, in load order
    sun: bool = False
    models: list[StaticModel] = field(default_factory=list)
    includes: list[str] = field(default_factory=list)
