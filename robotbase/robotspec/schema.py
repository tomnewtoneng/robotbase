"""The declarative robot spec (`robot.yaml`) — Robotbase's own format, versioned like the
scenario/manifest spec. The agent writes this; the compiler emits URDF/launch/manifest."""
from __future__ import annotations

import yaml
from pydantic import BaseModel, ValidationError


class RobotSpecError(ValueError):
    ...


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


class JointSpec(BaseModel):                  # arms (ignored by mobile archetypes)
    name: str
    type: str = "revolute"
    axis: str = "y"
    limits: list[float] = [-3.14, 3.14]
    controller: str = "position"
    gains: dict = {}


class RobotSpec(BaseModel):
    version: int = 1
    name: str = "warehouse_bot"
    base: str                                # differential-drive | fixed-arm | quadrotor
    body: Body = Body()
    drive: Drive = Drive()
    sensors: list[SensorSpec] = []
    joints: list[JointSpec] = []

    @classmethod
    def from_yaml(cls, path: str) -> "RobotSpec":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise RobotSpecError(str(e)) from e
