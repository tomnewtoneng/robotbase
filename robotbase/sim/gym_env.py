"""Scenarios as RL environments — *train and eval in one format*.

A Gymnasium environment over the in-process MuJoCo arm whose **task is a Robotbase scenario
goal**: reach a target joint configuration within tolerance — the very same target/tolerance
a `joint_positions_reached` assertion checks. So a policy is *trained* against this env and
*evaluated* against the identical scenario through the normal runner, closing the loop
between the eval layer and the policy-learning world. Optional deps: `mujoco`, `gymnasium`.
"""
from __future__ import annotations

import numpy as np

from robotbase.sim.mujoco_arm import ARM_XML

try:
    import gymnasium as gym
    from gymnasium import spaces
    _Base = gym.Env
except ImportError:  # keep the module importable without gymnasium
    gym = None
    spaces = None
    _Base = object


class RobotbaseArmEnv(_Base):
    """Reach a target joint configuration on the 2-DOF MuJoCo arm.

    - **Observation:** `[shoulder, elbow, shoulder_vel, elbow_vel]` (rad, rad/s).
    - **Action:** target angle for each joint (rad); a position controller tracks it.
    - **Reward:** dense, `-max_joint_error` each step, `+10` on reaching the goal.
    - **Terminated:** every joint within `tolerance` of its target. **Truncated:** `max_steps`.
    """

    metadata = {"render_modes": []}

    def __init__(self, target: dict | None = None, tolerance: float = 0.15,
                 max_steps: int = 200, substeps: int = 10):
        if gym is None:
            raise ImportError("RobotbaseArmEnv needs gymnasium (pip install robotbase[sim-rl]).")
        import mujoco

        super().__init__()
        self._mj = mujoco
        self.model = mujoco.MjModel.from_xml_string(ARM_XML)
        self.data = mujoco.MjData(self.model)
        self.joints = ["shoulder", "elbow"]
        target = target or {"shoulder": 1.0, "elbow": -1.4}
        self.target = np.array([target[j] for j in self.joints], dtype=np.float64)
        self.tolerance = tolerance
        self.max_steps = max_steps
        self.substeps = substeps
        self._steps = 0

        limit = np.array([3.14, 3.14], dtype=np.float32)
        self.action_space = spaces.Box(-limit, limit, dtype=np.float32)
        self.observation_space = spaces.Box(-np.inf, np.inf, shape=(4,), dtype=np.float32)

    def _jid(self, name):
        return self._mj.mj_name2id(self.model, self._mj.mjtObj.mjOBJ_JOINT, name)

    def _qpos(self):
        return np.array([self.data.qpos[self.model.jnt_qposadr[self._jid(j)]] for j in self.joints])

    def _obs(self):
        pos = [self.data.qpos[self.model.jnt_qposadr[self._jid(j)]] for j in self.joints]
        vel = [self.data.qvel[self.model.jnt_dofadr[self._jid(j)]] for j in self.joints]
        return np.array(pos + vel, dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._mj.mj_resetData(self.model, self.data)
        self._mj.mj_forward(self.model, self.data)
        self._steps = 0
        return self._obs(), {}

    def step(self, action):
        self.data.ctrl[:] = np.asarray(action, dtype=np.float64)
        for _ in range(self.substeps):
            self._mj.mj_step(self.model, self.data)
        self._steps += 1

        error = float(np.abs(self._qpos() - self.target).max())
        terminated = error <= self.tolerance
        reward = -error + (10.0 if terminated else 0.0)
        truncated = self._steps >= self.max_steps
        return self._obs(), reward, terminated, truncated, {"joint_error": error}
