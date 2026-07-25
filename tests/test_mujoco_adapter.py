"""Proves the sim-agnostic thesis: the SAME scenario runner, scenario format, assertions,
and result schema that drive the Gazebo runtime also drive a MuJoCo backend — no ROS, no
Docker, in-process. Skipped if mujoco isn't installed."""
import pytest

pytest.importorskip("mujoco")

from robotbase.scenario_runner import run_scenario  # noqa: E402
from robotbase.schema import ActionSpec, AssertionSpec, Scenario, SetupSpec  # noqa: E402
from robotbase.sim.base import SimAdapter  # noqa: E402
from robotbase.sim.mujoco_arm import MujocoArmAdapter  # noqa: E402


def _scenario():
    return Scenario(
        version=1,
        name="reach-configuration",
        setup=SetupSpec(reset_world=True),
        actions=[ActionSpec(type="wait", duration_seconds=3.0)],
        assertions=[AssertionSpec(
            type="joint_positions_reached",
            joint_targets={"shoulder": 1.0, "elbow": -1.4},
            joint_tolerance=0.15,
        )],
    )


def test_mujoco_adapter_satisfies_the_contract():
    assert isinstance(MujocoArmAdapter(), SimAdapter)


def test_scenario_runner_drives_mujoco_broken_then_fixed(tmp_path):
    # Broken controller: never commands the joints → arm droops → the scenario fails.
    broken = MujocoArmAdapter()
    broken.set_controller(lambda model, data: None)
    fail = run_scenario(_scenario(), broken, str(tmp_path))
    assert fail.passed is False

    # Correct controller: command the target angles → the arm reaches them → it passes.
    def control(model, data):
        data.ctrl[:] = [1.0, -1.4]

    fixed = MujocoArmAdapter()
    fixed.set_controller(control)
    ok = run_scenario(_scenario(), fixed, str(tmp_path))
    assert ok.passed is True
    # Same result schema as Gazebo: only the measured metrics appear (joint_positions).
    assert set(ok.metrics.joint_positions) == {"shoulder", "elbow"}
    assert ok.assertions[0].type == "joint_positions_reached"
