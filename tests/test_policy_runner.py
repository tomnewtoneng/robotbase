import math
import types

import pytest

import robotbase.container.policy_runner as pr


def _ns(**kw):
    return types.SimpleNamespace(**kw)


def test_yaw_from_quat_z_90deg():
    assert abs(pr.yaw_from_quat(0, 0, math.sin(math.pi / 4), math.cos(math.pi / 4)) - math.pi / 2) < 1e-6


def test_laserscan_decode():
    msg = _ns(ranges=[1.0, 2.0, float("inf")], angle_min=-1.0, angle_max=1.0, range_max=10.0)
    d = pr.laserscan(msg)
    assert d["ranges"] == [1.0, 2.0, float("inf")] and d["range_max"] == 10.0


def test_odom_pose_and_velocity():
    msg = _ns(pose=_ns(pose=_ns(position=_ns(x=1.0, y=2.0, z=3.0),
                                orientation=_ns(x=0.0, y=0.0, z=0.0, w=1.0))),
              twist=_ns(twist=_ns(linear=_ns(x=0.5, y=0.0, z=0.1), angular=_ns(z=0.2))))
    assert pr.odom_pose(msg) == {"x": 1.0, "y": 2.0, "z": 3.0, "yaw": 0.0}
    assert pr.odom_velocity(msg) == {"linear_x": 0.5, "linear_y": 0.0, "linear_z": 0.1, "angular_z": 0.2}


def test_jointstate_decode():
    msg = _ns(name=["shoulder_joint", "elbow_joint"], position=[1.0, -1.4])
    assert pr.jointstate(msg) == {"shoulder_joint": 1.0, "elbow_joint": -1.4}


def test_plan_publications_velocity():
    iface = {"kind": "velocity", "topic": "/cmd_vel",
             "keys": ["linear_x", "linear_y", "linear_z", "angular_z"]}
    pubs = pr.plan_publications(iface, {"linear_x": 0.3, "angular_z": 0.1})
    assert pubs == [{"topic": "/cmd_vel", "kind": "twist",
                     "fields": {"linear_x": 0.3, "linear_y": 0.0, "linear_z": 0.0, "angular_z": 0.1}}]


def test_plan_publications_joints():
    iface = {"kind": "joints", "joints": [
        {"name": "shoulder_joint", "command_topic": "/shoulder_cmd"},
        {"name": "elbow_joint", "command_topic": "/elbow_cmd"}]}
    pubs = pr.plan_publications(iface, {"shoulder_joint": 1.0, "elbow_joint": -1.4})
    assert {"topic": "/shoulder_cmd", "kind": "float64", "value": 1.0} in pubs
    assert {"topic": "/elbow_cmd", "kind": "float64", "value": -1.4} in pubs


def test_plan_publications_unknown_key_raises():
    iface = {"kind": "velocity", "topic": "/cmd_vel", "keys": ["linear_x", "angular_z"]}
    with pytest.raises(ValueError, match="spin"):
        pr.plan_publications(iface, {"spin": 5.0})
