"""The declarative world spec (`world.yaml`) — Robotbase's own format, compiled to Gazebo SDF."""
from __future__ import annotations

import yaml
from pydantic import BaseModel, Field, ValidationError


class WorldSpecError(ValueError):
    ...


class Obstacle(BaseModel):
    shape: str = "box"                       # box | cylinder
    size: list[float] = [0.3, 0.3, 0.5]
    at: list[float] = [0, 0, 0]              # x, y, z


class Wall(BaseModel):
    from_: list[float] = Field(alias="from")
    to: list[float]
    height: float = 0.5
    thickness: float = 0.1
    model_config = {"populate_by_name": True}


class Goal(BaseModel):
    name: str
    at: list[float]                          # x, y
    radius: float = 0.3


class WorldSpec(BaseModel):
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
