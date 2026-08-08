"""Generate a `policy.py` starter tailored to a project's robot interface."""
from __future__ import annotations

import os

import yaml

from robotbase.policy_interface import policy_interface

_HEADER = '''"""A Robotbase policy: act(obs) -> action, run via a scenario's `run_policy` action.
Point a scenario at it (replace its `run_node` action with `{type: run_policy, module: policy}`)
then `robotbase test <scenario>`. Load a trained model in __init__ if you have one.
See `robotbase describe` -> `policy_interface` for this robot's obs/action keys.
"""


class Policy:
    def __init__(self):
        # load your checkpoint / model here (runs once)
        pass

    def act(self, obs: dict) -> dict:
'''


def _body(iface: dict) -> str:
    if iface["action"]["kind"] == "velocity":
        return ('        # obs keys, e.g.: obs["scan"], obs["pose"], obs["velocity"]\n'
                '        return {"linear_x": 0.3, "angular_z": 0.0}\n')
    joints = ", ".join(f'"{j["name"]}": 0.0' for j in iface["action"]["joints"])
    return ('        # obs keys, e.g.: obs["joints"]\n'
            f'        return {{{joints}}}\n')


def write_policy_starter(project_dir: str) -> str:
    path = os.path.join(project_dir, "policy.py")
    if os.path.exists(path):
        raise FileExistsError(path)
    with open(os.path.join(project_dir, "robotbase.yaml")) as f:
        iface = policy_interface(yaml.safe_load(f) or {})
    with open(path, "w") as f:
        f.write(_HEADER + _body(iface))
    return path
