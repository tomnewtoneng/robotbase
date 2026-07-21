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
from robotbase.schema import Manifest, Scenario
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


@mcp.tool()
def project_describe() -> dict:
    """Describe the project's ROS/simulation configuration and scenarios."""
    info: dict = {"scenarios": sorted(_scenario_paths())}
    try:
        m = Manifest.from_yaml(os.path.join(PROJECT_DIR, "robotbase.yaml"))
        info.update(
            {
                "project": m.project_name,
                "ros_distribution": m.ros_distribution,
                "simulator": m.simulator,
                "launch_package": m.launch_package,
                "launch_file": m.launch_file,
                "mcp_port": m.mcp_port,
            }
        )
    except Exception as e:  # manifest optional/malformed — report, don't crash
        info["manifest_error"] = str(e)
    return info


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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
