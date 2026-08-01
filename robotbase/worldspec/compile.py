"""Compile a WorldSpec into a Gazebo SDF world (see docs/design/declarative-compiler.md).

Builds a typed WorldModel from the spec and renders it via the SDF backend. The world always loads
the base gz systems, unioned with the systems the robot's sensors require (passed in as
robot_systems) — the seam that keeps sensors declarative.
"""
from __future__ import annotations

import math

from robotbase.worldspec.schema import WorldSpec
from robotbase.worldspec.semantic import Box, Cylinder, Plane, StaticModel, WorldModel
from robotbase.worldspec.backends.sdf import render_sdf

_BASE_SYSTEMS = ["gz-sim-physics-system", "gz-sim-user-commands-system",
                 "gz-sim-scene-broadcaster-system"]
_GOAL_MATERIAL = "<material><ambient>0 1 0 0.3</ambient><diffuse>0 1 0 0.3</diffuse></material>"


def build_world_model(spec: WorldSpec, robot_systems=None) -> WorldModel:
    """Assemble a WorldSpec into a typed WorldModel (ground, obstacles, walls, goals — in that order,
    matching the SDF the compiler has always emitted)."""
    systems = list(_BASE_SYSTEMS)
    for s in (robot_systems or []):
        if s not in systems:
            systems.append(s)

    models: list[StaticModel] = []
    if spec.ground:
        models.append(StaticModel("ground_plane", Plane(), 0, 0, 0))
    for i, o in enumerate(spec.obstacles):
        if o.shape == "box":
            geom = Box([o.size[0], o.size[1], o.size[2]])
        else:
            geom = Cylinder(o.size[0], o.size[1])
        models.append(StaticModel(f"obstacle_{i}", geom, o.at[0], o.at[1], o.at[2]))
    for i, w in enumerate(spec.walls):
        ax, ay = w.from_
        bx, by = w.to
        length = math.hypot(bx - ax, by - ay)
        yaw = math.atan2(by - ay, bx - ax)
        models.append(StaticModel(f"wall_{i}", Box([length, w.thickness, w.height]),
                                  (ax + bx) / 2, (ay + by) / 2, w.height / 2, yaw))
    for g in spec.goals:
        models.append(StaticModel(f"goal_{g.name}", Cylinder(g.radius, 0.01),
                                  g.at[0], g.at[1], 0.005, has_collision=False, material=_GOAL_MATERIAL))

    return WorldModel(name=spec.name, systems=systems, sun=(spec.light == "sun"),
                      models=models, includes=list(spec.include))


def compile_world(spec: WorldSpec, robot_systems=None):
    """Compile to (sdf, metadata). Metadata carries the goals so the runner can score reach-goal."""
    world = build_world_model(spec, robot_systems)
    goals = {g.name: {"at": g.at, "radius": g.radius} for g in spec.goals}
    return render_sdf(world), {"goals": goals}
