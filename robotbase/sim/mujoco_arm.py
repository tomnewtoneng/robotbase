"""A MuJoCo backend: a fixed-base 2-DOF arm satisfying the SimAdapter contract entirely
in-process (no ROS, no Docker). Its purpose is to prove that the Robotbase scenario format,
scenario runner, assertions, and result schema are genuinely sim-agnostic — the very same
`run_scenario(...)` that drives the Gazebo runtime drives this too, producing the same
`ScenarioResult` with a `joint_positions_reached` assertion.

The agent's controller is a Python `control(model, data)` callback (MuJoCo's native control
model), mirroring the ROS controller the agent edits in a Gazebo project.
"""
from __future__ import annotations

import importlib.util

from robotbase.results import Metrics

# A 2-DOF arm: shoulder + elbow hinges (pitch), position actuators with damping so the arm
# reliably reaches and holds a commanded configuration against gravity.
ARM_XML = """
<mujoco>
  <option gravity="0 0 -9.81" timestep="0.002"/>
  <worldbody>
    <body name="upper" pos="0 0 1">
      <joint name="shoulder" type="hinge" axis="0 1 0" damping="3"/>
      <geom type="capsule" fromto="0 0 0 0 0 -0.4" size="0.035" mass="0.15"/>
      <body name="fore" pos="0 0 -0.4">
        <joint name="elbow" type="hinge" axis="0 1 0" damping="3"/>
        <geom type="capsule" fromto="0 0 0 0 0 -0.4" size="0.03" mass="0.15"/>
      </body>
    </body>
  </worldbody>
  <actuator>
    <position joint="shoulder" kp="120"/>
    <position joint="elbow" kp="90"/>
  </actuator>
</mujoco>
"""


class MujocoArmAdapter:
    """SimAdapter for a MuJoCo 2-DOF arm. Pass a `controller_path` (a .py exposing
    `control(model, data)`) or call `set_controller`. `joint_targets` in a
    `joint_positions_reached` assertion refer to the joint names ("shoulder", "elbow")."""

    def __init__(self, xml: str = ARM_XML, joints=("shoulder", "elbow"),
                 controller_path: str | None = None):
        import mujoco  # imported lazily: only needed for this backend

        self._mj = mujoco
        self.model = mujoco.MjModel.from_xml_string(xml)
        self.data = mujoco.MjData(self.model)
        self.joints = list(joints)
        self.controller = None
        if controller_path:
            self.load_controller(controller_path)

    # ---- controller ----------------------------------------------------
    def set_controller(self, fn) -> None:
        self.controller = fn

    def load_controller(self, path: str) -> None:
        spec = importlib.util.spec_from_file_location("rb_mujoco_controller", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.controller = getattr(module, "control", None)

    # ---- SimAdapter interface -----------------------------------------
    def reset(self) -> None:
        self._mj.mj_resetData(self.model, self.data)
        self._mj.mj_forward(self.model, self.data)

    def set_robot_pose(self, pose) -> None:
        pass  # fixed base — no mobile pose to set

    def spawn_box(self, obstacle) -> None:
        pass  # MuJoCo models are compiled; runtime obstacle spawning is unsupported here

    def run_action(self, action) -> None:
        # "wait" advances the sim (the controller runs each step). Other action types are
        # ignored — a backend need not support the ROS-centric verbs (run_node, etc.).
        if action.type == "wait":
            self._step(action.duration_seconds or 3.0)

    def _step(self, seconds: float) -> None:
        for _ in range(int(seconds / self.model.opt.timestep)):
            if self.controller is not None:
                self.controller(self.model, self.data)
            self._mj.mj_step(self.model, self.data)

    def collect_metrics(self) -> Metrics:
        positions = {}
        for name in self.joints:
            jid = self._mj.mj_name2id(self.model, self._mj.mjtObj.mjOBJ_JOINT, name)
            positions[name] = round(float(self.data.qpos[self.model.jnt_qposadr[jid]]), 4)
        return Metrics(joint_positions=positions)
