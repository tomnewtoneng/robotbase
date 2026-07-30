"""The declarative world spec (`world.yaml`) — Robotbase's own format, compiled to Gazebo SDF."""
from __future__ import annotations

import yaml
from pydantic import BaseModel, Field, ValidationError


class WorldSpecError(ValueError):
    ...


# extra="forbid" everywhere: an unknown key is almost always a wrong guess at the schema (e.g.
# an obstacle written {type, pose} instead of {shape, at}), and silently ignoring it — defaulting
# the position to the origin — is a dangerous silent failure. Reject it with a naming error instead.
class Obstacle(BaseModel):
    shape: str = "box"                       # box | cylinder
    size: list[float] = [0.3, 0.3, 0.5]
    at: list[float] = [0, 0, 0]              # x, y, z
    model_config = {"extra": "forbid"}


class Wall(BaseModel):
    from_: list[float] = Field(alias="from")
    to: list[float]
    height: float = 0.5
    thickness: float = 0.1
    model_config = {"populate_by_name": True, "extra": "forbid"}


class Goal(BaseModel):
    name: str
    at: list[float]                          # x, y
    radius: float = 0.3
    model_config = {"extra": "forbid"}


class WorldSpec(BaseModel):
    model_config = {"extra": "forbid"}
    version: int = 1
    name: str = "world"
    ground: bool = True
    light: str | None = "sun"
    obstacles: list[Obstacle] = []
    walls: list[Wall] = []
    goals: list[Goal] = []
    include: list[str] = []

    @classmethod
    def from_yaml(cls, path: str) -> "WorldSpec":
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise WorldSpecError(str(e)) from e
