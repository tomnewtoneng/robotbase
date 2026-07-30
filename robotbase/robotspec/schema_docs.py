"""A GENERAL, schema-derived authoring reference for robot.yaml / world.yaml.

This is the knowledge layer's source of truth: it introspects the actual Pydantic models and the
archetype/sensor registries, so it documents the FORMAT (fields, types, vocabulary) and can never
drift from the compiler or leak any specific task's answer. It is deliberately task-agnostic — the
same reference serves any authoring job, exactly like a provider's schema docs.
"""
from __future__ import annotations

from pydantic import BaseModel

from robotbase.robotspec.ir import SHAPE_SIZE
from robotbase.robotspec.modules import MODULES
from robotbase.robotspec.schema import Body, Drive, JointSpec, Part, RobotSpec, SensorSpec
from robotbase.robotspec.sensors import SENSORS
from robotbase.worldspec.schema import Goal, Obstacle, Wall, WorldSpec


def _type_name(annotation) -> str:
    s = getattr(annotation, "__name__", None) or str(annotation)
    return (s.replace("typing.", "").replace("robotbase.robotspec.schema.", "")
            .replace("robotbase.worldspec.schema.", "").replace("NoneType", "None"))


def _fields(model: type[BaseModel]) -> str:
    lines = []
    for name, f in model.model_fields.items():
        key = (f.alias or name) if f.alias else name
        default = "" if f.is_required() else f" = {f.default!r}"
        lines.append(f"    {key}: {_type_name(f.annotation)}{default}")
    return "\n".join(lines)


def authoring_reference() -> str:
    """Return a general markdown reference for the robot.yaml / world.yaml format."""
    return f"""# Robotbase Authoring Format Reference (robot.yaml / world.yaml)

You author two declarative specs; the compiler turns them into a runnable ROS 2 + Gazebo project.
The compiler validates strictly and its errors name the exact problem — an unknown key, a wrong
shape, or a wrong-length list. Trust the schema below and read the build error; don't guess.

**`size` depends on `shape`** (applies to a body and to a world obstacle):
{chr(10).join(f"    {s}: size = {fmt}" for s, (_n, fmt) in SHAPE_SIZE.items())}
Positions are `[x, y, z]` (obstacle `at`); 2-D points are `[x, y]` (wall `from`/`to`, goal `at`).

## robot.yaml  (compiled to URDF + launch + bridges)

{_fields(RobotSpec)}

`base` archetypes (each expands to a full drivetrain/body + its plugins/bridges):
    {", ".join(MODULES)}

`sensors[].type` (each adds the sensor link + gz sensor + ROS bridge + derived world system):
    {", ".join(SENSORS)}

Nested shapes:
  body:  {{ {_fields(Body).strip()} }}
  drive: {{ {_fields(Drive).strip()} }}
  sensors[]:  a list of:
{_fields(SensorSpec)}
  parts[]:  compose extra modules or raw links/joints (escape hatch); import a URDF with
            `use: custom` + `urdf: <path>`. Fields:
{_fields(Part)}
  joints[] (arms):
{_fields(JointSpec)}

## world.yaml  (compiled to SDF)

{_fields(WorldSpec)}

Nested shapes:
  obstacles[]:  {{ {_fields(Obstacle).strip()} }}   (shape: box | cylinder; size/at are [x,y,z])
  walls[]:      {{ {_fields(Wall).strip()} }}        (from/to are [x,y])
  goals[]:      {{ {_fields(Goal).strip()} }}        (at is [x,y])

## Common mistakes the compiler will reject (read the error — it names the field)

- An unknown key: the field name is wrong. Use the schema above (e.g. an obstacle is
  `{{shape, size, at}}`, not `{{type, pose}}`).
- A wrong-length `size`: it must match the `shape` (see the size table at the top).
- A sensor `on:` a link that does not exist: the error names the missing link. Sensors default to
  the primary base link (`base_link` for a differential-drive base).
- `base:` + `parts:` compose (the base is the first part) — they do not replace each other.

## Workflow

1. Edit robot.yaml and world.yaml to express the task.
2. Build — this recompiles the specs to URDF/SDF and builds the workspace.
3. Launch the simulation, then inspect the live ROS graph to VERIFY your robot: it must spawn as
   the Gazebo model `robot`, accept `/cmd_vel`, and publish the sensor topics you declared
   (`/scan` for lidar, `/image` for camera). Do not claim success until you have confirmed this
   from the running system.
"""


def authoring_json_schema() -> dict:
    """The robot.yaml / world.yaml JSON Schemas, straight from the Pydantic models — for editors,
    programmatic validation, or an agent that prefers structured schema over prose."""
    return {"robot.yaml": RobotSpec.model_json_schema(),
            "world.yaml": WorldSpec.model_json_schema()}
