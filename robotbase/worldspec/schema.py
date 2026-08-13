"""The declarative world spec (`world.yaml`) — Robotbase's own format, compiled to Gazebo SDF."""
from __future__ import annotations

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from robotbase.robotspec.ir import SHAPE_SIZE
from robotbase.robotspec.schema import _check_len


class WorldSpecError(ValueError):
    ...


# extra="forbid" everywhere: an unknown key is almost always a wrong guess at the schema (e.g.
# an obstacle written {type, pose} instead of {shape, at}), and silently ignoring it — defaulting
# the position to the origin — is a dangerous silent failure. Reject it with a naming error instead.
class Obstacle(BaseModel):
    shape: str = "box"                       # box | cylinder
    size: list[float] = [0.3, 0.3, 0.5]      # box [x,y,z] / cylinder [radius, length]
    at: list[float] = [0, 0, 0]              # x, y, z
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check(self):
        if self.shape not in ("box", "cylinder"):
            raise ValueError(f"obstacle shape must be box or cylinder, got {self.shape!r}")
        need, fmt = SHAPE_SIZE[self.shape]
        _check_len(self.size, need, f"obstacle {self.shape} size {fmt}")
        _check_len(self.at, 3, "obstacle at [x, y, z]")
        return self


class Wall(BaseModel):
    from_: list[float] = Field(alias="from")
    to: list[float]
    height: float = 0.5
    thickness: float = 0.1
    model_config = {"populate_by_name": True, "extra": "forbid"}

    @model_validator(mode="after")
    def _check(self):
        _check_len(self.from_, 2, "wall from [x, y]")
        _check_len(self.to, 2, "wall to [x, y]")
        if self.from_ == self.to:
            raise ValueError(f"wall has zero length: from and to are the same point {self.from_} "
                             "— give it two distinct endpoints")
        return self


class Goal(BaseModel):
    name: str
    at: list[float]                          # x, y
    radius: float = 0.3
    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check(self):
        _check_len(self.at, 2, "goal at [x, y]")
        return self


class WorldSpec(BaseModel):
    model_config = {"extra": "forbid"}
    version: int = 1
    name: str = "world"
    ground: bool = True
    light: str | None = "sun"
    spawn: list[float] = [0.0, 0.0]          # robot start [x, y] for a bare launch (scenarios override)
    obstacles: list[Obstacle] = []
    walls: list[Wall] = []
    goals: list[Goal] = []
    include: list[str] = []

    @model_validator(mode="after")
    def _check(self):
        _check_len(self.spawn, 2, "spawn [x, y]")
        return self

    @classmethod
    def from_yaml(cls, path: str) -> "WorldSpec":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise WorldSpecError(str(e)) from e
