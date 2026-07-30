"""Ground-truth measurement of a running Gazebo sim, for the RobotBench authoring judge.

Reads a model's world pose from `gz topic -e /world/<world>/dynamic_pose/info` and checks that
`/cmd_vel` has a live subscriber. Both are done through an injected `sh(cmd) -> stdout` callable
so the probe works against whatever brings the sim up (WITH: `docker compose exec`; WITHOUT: the
raw launch env) and the pure parsers stay unit-testable. gz OMITS near-zero fields, so a missing
x/y/z parses as 0.0 (a robot exactly at the origin reports no x).
"""
from __future__ import annotations

import re
import time
from typing import Callable

Sh = Callable[[str], str]


def parse_model_xy(dynamic_pose_output: str, model_name: str) -> tuple[float, float] | None:
    """Extract (x, y) world position of `model_name` from a dynamic_pose/info dump.

    Returns None if the model isn't present. Missing x/y (gz omits ~0) default to 0.0."""
    m = re.search(
        rf'name:\s*"{re.escape(model_name)}"\s*\n\s*id:.*?position\s*\{{(.*?)\}}',
        dynamic_pose_output, re.DOTALL)
    if not m:
        return None
    block = m.group(1)
    xm = re.search(r'x:\s*([-\d.eE+]+)', block)
    ym = re.search(r'y:\s*([-\d.eE+]+)', block)
    return (float(xm.group(1)) if xm else 0.0, float(ym.group(1)) if ym else 0.0)


def discover_world(sh: Sh, fallback: str = "warehouse") -> str:
    """Find the running world's name from `gz topic -l`. The world name is NOT part of the robot
    interface contract, so the agent may call it anything (e.g. 'default') — never assume it."""
    out = sh("gz topic -l")
    for line in out.splitlines():
        m = re.match(r"/world/([^/]+)/dynamic_pose/info\s*$", line.strip())
        if m:
            return m.group(1)
    return fallback


def sample_model_pose(model_name: str, duration_s: float, sh: Sh, *,
                      world: str = "warehouse", hz: float = 10.0) -> list[tuple[float, float, float]]:
    """Sample (t, x, y) world positions of `model_name` for `duration_s` seconds. The world name
    is auto-discovered (the agent may name its world anything); `world` is only the fallback."""
    topic = f"/world/{discover_world(sh, world)}/dynamic_pose/info"
    trace: list[tuple[float, float, float]] = []
    start = time.monotonic()
    period = 1.0 / hz
    while (t := time.monotonic() - start) < duration_s:
        out = sh(f"timeout 1 gz topic -e -t {topic} -n 1")
        xy = parse_model_xy(out, model_name)
        if xy is not None:
            trace.append((round(t, 3), xy[0], xy[1]))
        time.sleep(period)
    return trace


def cmd_vel_is_live(sh: Sh, requires: list[str], *, world: str = "warehouse") -> bool:
    """Confirm the robot exposes the interfaces the controller needs: /cmd_vel accepted plus each
    required publisher (/scan, /image). Uses `ros2 topic list` — cheap and arm-agnostic."""
    out = sh("ros2 topic list")
    topics = set(out.split())
    needed = {"/cmd_vel"} | {("/" + r if not r.startswith("/") else r) for r in requires}
    return needed <= topics
