"""The sim-adapter contract.

Robotbase's durable value is the *contract*, not the simulator underneath it: the scenario
runner, the scenario/manifest/result format, the assertions, and the metrics are all
sim-agnostic. They drive any backend that satisfies this interface. `runtime.Runtime`
(Gazebo Harmonic + ROS 2, in Docker) is one implementation; `sim.mujoco_arm.MujocoArmAdapter`
(MuJoCo, in-process, no ROS/Docker) is another. That is what makes Robotbase "the layer over
sims" rather than a Gazebo tool — the same `run_scenario(scenario, adapter, run_dir)` works
against both.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from robotbase.results import Metrics


@runtime_checkable
class SimAdapter(Protocol):
    """What `robotbase.scenario_runner.run_scenario` requires of a backend."""

    def reset(self) -> None:
        """Return the simulation to a pristine starting state."""

    def set_robot_pose(self, pose) -> None:
        """Place the robot at the scenario's start pose (no-op for a fixed-base robot)."""

    def spawn_box(self, obstacle) -> None:
        """Add a box obstacle from the scenario setup (no-op where unsupported)."""

    def run_action(self, action) -> None:
        """Execute one scenario action (e.g. run the controller, wait). Unknown action
        types should be ignored, not fatal — different backends support different verbs."""

    def collect_metrics(self) -> Metrics:
        """Return the whole-episode metrics used to evaluate the assertions."""

    # Optional: finalize_episode(dest_dir: str) -> dict | None — for backends that record an
    # MCAP episode (Gazebo does; MuJoCo doesn't). run_scenario calls it only if present.
