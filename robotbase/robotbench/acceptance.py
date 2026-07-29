"""Canonical acceptance specs + pure predicate logic for the RobotBench v2 authoring judge.

An `AcceptanceSpec` says, for one `judge_scenario`: where the world's obstacles are, how far to
jitter the seeded spawn poses, how long to run, which robot interfaces must be live, and — the
heart of it — a **pure predicate** that decides pass/fail from a ground-truth pose trace. The
predicate reads only the robot's Gazebo world pose (never its own /scan or /odom), so a robot that
mis-reports its own sensors cannot fake a pass.

Trace convention: `sample_model_pose` yields `(t, x, y)`. `min_distance_to` takes points whose
first two elements are `(x, y)`, so predicates strip the timestamp before calling it. Distances are
to the obstacle **centre** (the bands below are calibrated on centre distance, not face gap).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable

# (x, y, half_extent) per obstacle name.
Obstacles = dict[str, tuple[float, float, float]]
Trace = list[tuple[float, float, float]]


def min_distance_to(points, ox: float, oy: float) -> float:
    """Closest Euclidean approach of a path to (ox, oy). `points` elements are (x, y, ...)."""
    return min(math.hypot(p[0] - ox, p[1] - oy) for p in points)


def _xy(trace: Trace):
    return [(x, y) for (_t, x, y) in trace]


@dataclass(frozen=True)
class AcceptanceSpec:
    world_obstacles: Obstacles
    spawn_range: tuple[float, float]        # (x_jitter, y_jitter) around the base spawn
    duration_s: float
    requires: list[str]                     # robot interfaces that must be live, e.g. ["scan"]
    predicate: Callable[[Trace, Obstacles], bool]


def spawn_pose(spec: AcceptanceSpec, seed: int) -> tuple[float, float, float]:
    """Deterministic per-seed spawn jitter within `spec.spawn_range` (same seed → same pose)."""
    rng = random.Random(seed)
    jx, jy = spec.spawn_range
    return (round(rng.uniform(-jx, jx), 4), round(rng.uniform(-jy, jy), 4), 0.0)


def _stop_band(target: str, band=(0.8, 1.2), floor: float = 0.4):
    """Passed the task if the closest approach to `target`'s centre lands in `band` and the robot
    never penetrated past `floor` (a collision)."""
    def predicate(trace: Trace, obstacles: Obstacles) -> bool:
        ox, oy, _ = obstacles[target]
        d = min_distance_to(_xy(trace), ox, oy)
        return band[0] <= d <= band[1] and d >= floor
    return predicate


def _mast_clear():
    """Passed if the robot drove *past* the low barrier (its short mast-mounted LiDAR shouldn't see
    it — closest approach < 0.5) yet stopped ~1 m before the tall box it *should* see."""
    def predicate(trace: Trace, obstacles: Obstacles) -> bool:
        pts = _xy(trace)
        lox, loy, _ = obstacles["low_barrier"]
        tox, toy, _ = obstacles["tall_box"]
        passed_low = min_distance_to(pts, lox, loy) < 0.5
        stopped_tall = 0.8 <= min_distance_to(pts, tox, toy) <= 1.2
        return passed_low and stopped_tall
    return predicate


SPECS: dict[str, AcceptanceSpec] = {
    "author_stop_at_1m": AcceptanceSpec(
        world_obstacles={"box": (2.0, 0.0, 0.25)},
        spawn_range=(0.3, 0.3), duration_s=12.0, requires=["scan"],
        predicate=_stop_band("box"),
    ),
    "author_mast_clear": AcceptanceSpec(
        world_obstacles={"low_barrier": (2.0, 0.0, 0.1), "tall_box": (3.5, 0.0, 0.25)},
        spawn_range=(0.3, 0.3), duration_s=16.0, requires=["scan"],
        predicate=_mast_clear(),
    ),
    "author_two_sensor": AcceptanceSpec(
        world_obstacles={"box": (2.0, 0.0, 0.25)},
        spawn_range=(0.3, 0.3), duration_s=12.0, requires=["scan", "image"],
        predicate=_stop_band("box"),
    ),
}
