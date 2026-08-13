"""The declarative robot spec (`robot.yaml`) — Robotbase's own format, versioned like the
scenario/manifest spec. The agent writes this; the compiler emits URDF/launch/manifest."""
from __future__ import annotations

import yaml
from pydantic import BaseModel, ValidationError, model_validator

from robotbase.robotspec.ir import SHAPE_SIZE   # single source of truth for shape -> size length


class RobotSpecError(ValueError):
    ...


def _check_len(value, n: int, what: str) -> None:
    if len(value) != n:
        raise ValueError(f"{what} must have {n} value{'s' if n != 1 else ''}, got {len(value)}: {list(value)}")


_BOOL_KEY = {True: "on", False: "off"}   # YAML 1.1 coerces on/off/yes/no keys to bools


def _normalise_bool_keys(node):
    """Undo YAML 1.1's coercion of on/off/yes/no *keys* to bools (e.g. sensor `on:`)."""
    if isinstance(node, dict):
        return {(_BOOL_KEY[k] if isinstance(k, bool) else k): _normalise_bool_keys(v)
                for k, v in node.items()}
    if isinstance(node, list):
        return [_normalise_bool_keys(v) for v in node]
    return node


# extra="forbid": an unknown key (e.g. a sensor written with `enabled:` or `pose:`) is a wrong
# guess at the schema; erroring names the bad field instead of silently dropping it. Raw `links`/
# `joints` on a Part stay free-form dicts (the escape hatch) — only the typed models are strict.
class Body(BaseModel):
    shape: str = "box"                       # box | cylinder | sphere
    size: list[float] = [0.35, 0.30, 0.15]   # metres; box [x,y,z] / cylinder [r,l] / sphere [r]
    mass: float = 5.0
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check(self):
        if self.shape not in SHAPE_SIZE:
            raise ValueError(f"body shape must be one of {sorted(SHAPE_SIZE)}, got {self.shape!r}")
        need, fmt = SHAPE_SIZE[self.shape]
        _check_len(self.size, need, f"body {self.shape} size {fmt}")
        return self


class Drive(BaseModel):                      # differential-drive params
    wheel_radius: float = 0.05
    wheel_separation: float = 0.34
    model_config = {"extra": "forbid"}


class SensorSpec(BaseModel):
    type: str                                # lidar | camera | depth | imu | contact
    mount: list[float] | None = None         # [x,y,z] on the mount link; sensible default per type
    resolution: list[int] | None = None      # camera/depth [width, height]
    topic: str | None = None                 # override the default ROS topic
    on: str | None = None                    # link to mount to; defaults to the primary base link
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check(self):
        if self.mount is not None:
            _check_len(self.mount, 3, "sensor mount [x, y, z]")
        if self.resolution is not None:
            _check_len(self.resolution, 2, "sensor resolution [width, height]")
        return self


class JointSpec(BaseModel):                  # arms (ignored by mobile archetypes)
    name: str
    type: str = "revolute"
    axis: str = "y"
    limits: list[float] = [-3.14, 3.14]
    controller: str = "position"
    gains: dict = {}
    model_config = {"extra": "forbid"}


class JointControl(BaseModel):               # per-joint controller tuning (PID gains)
    p: int | float | None = None             # int|float preserves the user's numeric form (120 -> "120")
    i: int | float | None = None
    d: int | float | None = None
    model_config = {"extra": "forbid"}


class BaseControl(BaseModel):                # drive/velocity controller tuning (non-geometry knobs)
    odom_publish_frequency: int | float | None = None
    topic: str | None = None
    odom_topic: str | None = None
    tf_topic: str | None = None
    model_config = {"extra": "forbid"}


class ControlSpec(BaseModel):                # declarative control config (the vision's Controller IR)
    joints: dict[str, JointControl] = {}     # keyed by joint name, e.g. shoulder_joint
    base: BaseControl | None = None
    model_config = {"extra": "forbid"}


class Part(BaseModel):
    use: str | None = None                   # a module name (or "custom"); None => raw part
    mount: dict | None = None                # {to: link, xyz: [...], rpy: [...]}
    body: Body | None = None
    drive: Drive | None = None
    links: list[dict] = []                   # raw links: {name, shape, size, mass} or {name, xml}
    joints: list[dict] = []                  # raw joints: {name, parent, child, type, xyz, rpy, axis}
    urdf: str | None = None                  # for use: custom (import) — a later task uses this
    model_config = {"extra": "forbid"}


class RobotSpec(BaseModel):
    model_config = {"extra": "forbid"}
    version: int = 1
    name: str = "warehouse_bot"
    base: str | None = None                  # differential-drive | fixed-arm | quadrotor
    body: Body = Body()
    drive: Drive = Drive()
    sensors: list[SensorSpec] = []
    joints: list[JointSpec] = []
    parts: list[Part] = []
    control: ControlSpec | None = None       # tune the compiled control plugins (gains, odom rate)

    @classmethod
    def from_yaml(cls, path: str) -> "RobotSpec":
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise RobotSpecError(f"{path} is not valid YAML: {e}") from e
        data = _normalise_bool_keys(data)
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise RobotSpecError(str(e)) from e
