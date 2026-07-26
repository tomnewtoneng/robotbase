"""The declarative robot spec (`robot.yaml`) — Robotbase's own format, versioned like the
scenario/manifest spec. The agent writes this; the compiler emits URDF/launch/manifest."""
from __future__ import annotations

import yaml
from pydantic import BaseModel, ValidationError


class RobotSpecError(ValueError):
    ...


_BOOL_KEY = {True: "on", False: "off"}   # YAML 1.1 coerces on/off/yes/no keys to bools


def _normalise_bool_keys(node):
    """Undo YAML 1.1's coercion of on/off/yes/no *keys* to bools (e.g. sensor `on:`)."""
    if isinstance(node, dict):
        return {(_BOOL_KEY[k] if isinstance(k, bool) else k): _normalise_bool_keys(v)
                for k, v in node.items()}
    if isinstance(node, list):
        return [_normalise_bool_keys(v) for v in node]
    return node


class Body(BaseModel):
    shape: str = "box"                       # box | cylinder
    size: list[float] = [0.35, 0.30, 0.15]   # metres; x,y,z for box
    mass: float = 5.0


class Drive(BaseModel):                      # differential-drive params
    wheel_radius: float = 0.05
    wheel_separation: float = 0.34


class SensorSpec(BaseModel):
    type: str                                # lidar | camera | depth | imu | contact
    mount: list[float] | None = None         # xyz on base_link; sensible default per type
    resolution: list[int] | None = None      # camera/depth
    topic: str | None = None                 # override the default ROS topic
    on: str | None = None                    # link to mount to; defaults to the primary base link


class JointSpec(BaseModel):                  # arms (ignored by mobile archetypes)
    name: str
    type: str = "revolute"
    axis: str = "y"
    limits: list[float] = [-3.14, 3.14]
    controller: str = "position"
    gains: dict = {}


class Part(BaseModel):
    use: str | None = None                   # a module name (or "custom"); None => raw part
    mount: dict | None = None                # {to: link, xyz: [...], rpy: [...]}
    body: Body | None = None
    drive: Drive | None = None
    links: list[dict] = []                   # raw links: {name, shape, size, mass} or {name, xml}
    joints: list[dict] = []                  # raw joints: {name, parent, child, type, xyz, rpy, axis}
    urdf: str | None = None                  # for use: custom (import) — a later task uses this


class RobotSpec(BaseModel):
    version: int = 1
    name: str = "warehouse_bot"
    base: str | None = None                  # differential-drive | fixed-arm | quadrotor
    body: Body = Body()
    drive: Drive = Drive()
    sensors: list[SensorSpec] = []
    joints: list[JointSpec] = []
    parts: list[Part] = []

    @classmethod
    def from_yaml(cls, path: str) -> "RobotSpec":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        data = _normalise_bool_keys(data)
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise RobotSpecError(str(e)) from e
