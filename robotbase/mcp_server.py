"""MCP server exposing Robotbase's loop-closing tools to a coding agent.

Thin wrapper over the in-process Runtime and scenario runner. Binds to stdio
(localhost only); returns structured, size-bounded responses. The project it
operates on is taken from ROBOTBASE_PROJECT_DIR (default: current directory).
"""
from __future__ import annotations

import glob
import json
import os

from mcp.server.fastmcp import FastMCP

from robotbase.runtime import Runtime
from robotbase.schema import Scenario
from robotbase.scenario_runner import run_scenario

PROJECT_DIR = os.environ.get("ROBOTBASE_PROJECT_DIR", ".")
RUN_DIR = os.path.join(PROJECT_DIR, ".robotbase", "runs")


def validate_scenario_name(name: str, available: list[str]) -> None:
    if name not in available:
        raise ValueError(f"Unknown scenario {name!r}. Available: {sorted(available)}")


def _scenario_paths() -> dict[str, str]:
    directory = os.path.join(PROJECT_DIR, "simulation", "scenarios")
    return {
        os.path.splitext(os.path.basename(p))[0]: p
        for p in glob.glob(os.path.join(directory, "*.yaml"))
    }


mcp = FastMCP("robotbase")
_runtime = Runtime(PROJECT_DIR)
# Human opt-in: set ROBOTBASE_GUI=foxglove before launching the agent to watch
# its scenario runs live in Foxglove. Defaults to headless; the agent never
# chooses this, so determinism/performance are unaffected unless a human asks.
_runtime.gui = os.environ.get("ROBOTBASE_GUI", "none")


@mcp.tool()
def project_describe() -> dict:
    """Report structured ground truth for the project: the robot (dimensions, joints,
    sensors, control topics), the world (models + arena bounds), and the scenarios (each
    with its description and assertions). Prefer this over reading URDF/world files."""
    from robotbase.describe import describe

    try:
        return describe(PROJECT_DIR)
    except Exception as e:  # manifest/files optional or malformed — report, don't crash
        return {"error": str(e)}


@mcp.tool()
def environment_doctor() -> dict:
    """Check the environment for common problems (Docker reachable, the runtime image built,
    port 8765 conflicts, whether this project's container is up) and suggest fixes. Run this
    first if build/launch/test operations are failing for infrastructure reasons."""
    from robotbase.doctor import diagnose_environment

    return diagnose_environment(PROJECT_DIR)


@mcp.tool()
def workspace_build(clean: bool = False) -> dict:
    """Build the ROS workspace; returns pass/fail, duration, and parsed errors."""
    return _runtime.build(clean=clean)


@mcp.tool()
def simulation_launch() -> dict:
    """Start the headless simulation and wait until the ROS graph is ready."""
    return _runtime.launch()


@mcp.tool()
def simulation_stop() -> dict:
    """Stop the running simulation."""
    return _runtime.stop()


@mcp.tool()
def simulation_reset() -> dict:
    """Reset the simulation to a clean starting state (teardown + relaunch)."""
    return _runtime.reset()


@mcp.tool()
def simulation_get_status() -> dict:
    """Report whether the sim is running and the ROS graph is ready."""
    return _runtime.simulation_status()


@mcp.tool()
def ros_list_topics() -> list[dict]:
    """List active ROS topics with their message types."""
    return _runtime.list_topics()


@mcp.tool()
def ros_inspect_topic(
    topic: str, duration_seconds: float = 2.0, maximum_messages: int = 3
) -> dict:
    """Sample a ROS topic and return a bounded structured excerpt."""
    return _runtime.inspect_topic(topic, duration_seconds, maximum_messages)


@mcp.tool()
def scenario_list() -> list[str]:
    """List available scenario names."""
    return sorted(_scenario_paths())


@mcp.tool()
def scenario_run(name: str) -> dict:
    """Run a scenario end-to-end and return the structured result."""
    paths = _scenario_paths()
    validate_scenario_name(name, list(paths))
    scenario = Scenario.from_yaml(paths[name])
    return run_scenario(scenario, _runtime, RUN_DIR).model_dump()


@mcp.tool()
def scenario_get_result(run_id: str) -> dict:
    """Return the stored structured result for a prior scenario run."""
    path = os.path.join(RUN_DIR, run_id, "result.json")
    if not os.path.exists(path):
        raise ValueError(f"No result for run_id {run_id!r}")
    with open(path) as f:
        return json.load(f)


@mcp.tool()
def diagnose_run(run_id: str = "latest") -> dict:
    """Explain why a run failed, in plain language: correlate the failed assertions with the
    episode events (collision, closest approach) and the control behavior at the failure.
    Use this right after a failing scenario_run to decide what to change in the controller."""
    from robotbase.diagnose import collision_time, diagnose

    if run_id in ("latest", ""):
        dirs = [d for d in glob.glob(os.path.join(RUN_DIR, "*")) if os.path.isdir(d)]
        if not dirs:
            return {"error": "no runs found"}
        run_id = os.path.basename(max(dirs, key=os.path.getmtime))
    result_path = os.path.join(RUN_DIR, run_id, "result.json")
    if not os.path.exists(result_path):
        return {"error": f"no result for run {run_id!r}"}
    with open(result_path) as f:
        result = json.load(f)
    events, control = [], None
    try:
        events = _runtime.episode_events(run_id).get("events", [])
        ct = collision_time(events)
        if ct is not None:
            q = _runtime.episode_query(run_id, "/cmd_vel", around=ct, window=0.5, max_samples=1)
            control = q["samples"][-1] if q.get("samples") else None
    except Exception:
        pass
    return diagnose(result, events, control)


@mcp.tool()
def episode_summary(run_id: str = "latest") -> dict:
    """Summarize a recorded run's MCAP episode: topics, message counts, duration.

    run_id defaults to the most recent run. Use this first to see what was recorded.
    """
    return _runtime.episode_summary(run_id)


@mcp.tool()
def episode_events(run_id: str = "latest") -> dict:
    """Return the derived event timeline for a run (e.g. collision) with timestamps."""
    return _runtime.episode_events(run_id)


@mcp.tool()
def episode_query(
    topic: str,
    run_id: str = "latest",
    around: float | None = None,
    window: float = 2.0,
    max_samples: int = 40,
) -> dict:
    """Return a bounded, downsampled slice of one topic from a recorded episode.

    Give a time of interest via `around` (seconds from episode start, e.g. a collision
    timestamp from episode_events) and a `window` to inspect around it — the way to see
    what a topic (e.g. /scan, /cmd_vel, /odom) was doing at a moment, without a raw dump.
    """
    return _runtime.episode_query(run_id, topic, around, window, max_samples)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
