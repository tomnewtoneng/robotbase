"""The gym env is an optional frontier feature; skipped unless mujoco + gymnasium are installed."""
import numpy as np
import pytest

pytest.importorskip("mujoco")
pytest.importorskip("gymnasium")

from gymnasium.utils.env_checker import check_env  # noqa: E402

from robotbase.sim.gym_env import RobotbaseArmEnv  # noqa: E402


def test_conforms_to_the_gym_api():
    check_env(RobotbaseArmEnv(max_steps=20), skip_render_check=True)


def test_reset_and_step_shapes():
    env = RobotbaseArmEnv()
    obs, info = env.reset(seed=0)
    assert obs.shape == (4,) and isinstance(info, dict)
    obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
    assert obs.shape == (4,)
    assert isinstance(reward, float) and "joint_error" in info


def test_target_holding_policy_reaches_the_goal():
    # The task's goal is the scenario goal: reach shoulder=1.0, elbow=-1.4 within tolerance.
    env = RobotbaseArmEnv(target={"shoulder": 1.0, "elbow": -1.4}, tolerance=0.15, max_steps=300)
    env.reset(seed=0)
    action = np.array([1.0, -1.4], dtype=np.float32)   # hold the target setpoints
    terminated = False
    for _ in range(env.max_steps):
        _obs, _r, terminated, truncated, _info = env.step(action)
        if terminated or truncated:
            break
    assert terminated is True   # a correct policy reaches the same goal the assertion checks
