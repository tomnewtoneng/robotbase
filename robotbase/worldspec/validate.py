"""World-side static validation — catch a dangerous world/spawn combination BEFORE launching.

The robot compiler already validates the robot's own physics; this validates the *placement*: a
robot whose start pose sits inside a wall or obstacle spawns in penetration — physics ejects it
unpredictably, the lidar reads from the wrong spot, and any collision assertion is meaningless.
Findings reuse the robotspec Finding type so they render alongside robot findings in `validate`.
"""
from __future__ import annotations

import math

from robotbase.robotspec.validate import Finding
from robotbase.worldspec.compile import build_world_model
from robotbase.worldspec.schema import WorldSpec
from robotbase.worldspec.semantic import Box

# A generous mobile-base footprint radius (m). The check is a safety net, so it errs toward flagging
# a spawn that merely grazes a wall rather than missing a real overlap.
DEFAULT_FOOTPRINT_M = 0.25


def validate_spawn(spec: WorldSpec, footprint_m: float = DEFAULT_FOOTPRINT_M) -> list[Finding]:
    """Flag a robot spawn point that overlaps any collidable box (wall/obstacle) in the world."""
    sx, sy = spec.spawn[0], spec.spawn[1]
    findings: list[Finding] = []
    for m in build_world_model(spec).models:
        if not m.has_collision or not isinstance(m.geometry, Box):
            continue
        hx, hy = m.geometry.size[0] / 2.0, m.geometry.size[1] / 2.0
        c, s = abs(math.cos(m.yaw)), abs(math.sin(m.yaw))
        ax = hx * c + hy * s          # yaw-aware world-x half-extent (AABB of the rotated box)
        ay = hx * s + hy * c
        if abs(sx - m.x) <= ax + footprint_m and abs(sy - m.y) <= ay + footprint_m:
            findings.append(Finding(
                "error", "spawn-inside-object",
                f"robot spawn ({sx:g}, {sy:g}) overlaps {m.name} — the robot starts inside a solid "
                f"object. Set a clear `spawn: [x, y]` in world.yaml or move the wall/obstacle."))
    return findings
