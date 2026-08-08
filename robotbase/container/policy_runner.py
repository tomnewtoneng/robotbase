"""Self-contained policy runner — runs INSIDE the ROS container (no `robotbase` package there).
It imports the user's policy module, subscribes to the robot's observation topics, and on a
sim-time timer builds `obs`, calls `policy.act(obs)`, and publishes the encoded action.

ROS imports are function-local so the pure decode/encode helpers below stay host-importable and
unit-tested. Invoked by runtime.run_action via:
    python3 /workspace/.robotbase/policy_runner.py --interface <json> --module policy --class Policy --rate 10
with the ROS env sourced and --ros-args -p use_sim_time:=true.
"""
from __future__ import annotations

import math


def yaw_from_quat(x: float, y: float, z: float, w: float) -> float:
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def laserscan(msg) -> dict:
    return {"ranges": list(msg.ranges), "angle_min": msg.angle_min,
            "angle_max": msg.angle_max, "range_max": msg.range_max}


def odom_pose(msg) -> dict:
    p = msg.pose.pose.position
    o = msg.pose.pose.orientation
    return {"x": p.x, "y": p.y, "z": p.z, "yaw": yaw_from_quat(o.x, o.y, o.z, o.w)}


def odom_velocity(msg) -> dict:
    t = msg.twist.twist
    return {"linear_x": t.linear.x, "linear_y": t.linear.y,
            "linear_z": t.linear.z, "angular_z": t.angular.z}


def jointstate(msg) -> dict:
    return {n: p for n, p in zip(msg.name, msg.position)}


def imu(msg) -> dict:
    o, a, l = msg.orientation, msg.angular_velocity, msg.linear_acceleration
    return {"orientation": {"x": o.x, "y": o.y, "z": o.z, "w": o.w},
            "angular_velocity": {"x": a.x, "y": a.y, "z": a.z},
            "linear_acceleration": {"x": l.x, "y": l.y, "z": l.z}}


def image(msg):
    """Decode a sensor_msgs/Image to an HxWx3 uint8 numpy array (rgb8/bgr8). Container-only
    (needs numpy); not host-unit-tested."""
    import numpy as np
    arr = np.frombuffer(bytes(msg.data), dtype=np.uint8)
    channels = 3
    return arr.reshape((msg.height, msg.width, channels))


def plan_publications(action_iface: dict, action: dict) -> list[dict]:
    """Validate the policy's returned action dict against the robot's interface and return the
    intended publications. Raises ValueError naming any key that isn't part of the interface."""
    if action_iface["kind"] == "velocity":
        allowed = set(action_iface["keys"])
        bad = set(action or {}) - allowed
        if bad:
            raise ValueError(f"unknown action key(s) {sorted(bad)}; expected {sorted(allowed)}")
        fields = {k: float((action or {}).get(k, 0.0)) for k in action_iface["keys"]}
        return [{"topic": action_iface["topic"], "kind": "twist", "fields": fields}]
    # joints
    by_name = {j["name"]: j["command_topic"] for j in action_iface["joints"]}
    bad = set(action or {}) - set(by_name)
    if bad:
        raise ValueError(f"unknown joint(s) {sorted(bad)}; expected {sorted(by_name)}")
    return [{"topic": by_name[name], "kind": "float64", "value": float(val)}
            for name, val in (action or {}).items()]


def _obs_builder(observation):
    """Map obs-key -> (topic, decoder). Odometry's two keys resolve to pose/velocity decoders."""
    per_key = {"scan": laserscan, "pose": odom_pose, "velocity": odom_velocity,
               "joints": jointstate, "imu": imu, "image": image}
    return {o["key"]: (o["topic"], per_key[o["key"]])
            for o in observation if o["key"] in per_key}


def main():
    import argparse
    import importlib
    import json
    import sys

    import rclpy
    from geometry_msgs.msg import Twist
    from rclpy.node import Node
    from rosidl_runtime_py.utilities import get_message
    from std_msgs.msg import Float64

    ap = argparse.ArgumentParser()
    ap.add_argument("--interface", required=True)     # JSON string
    ap.add_argument("--module", default="policy")
    ap.add_argument("--class", dest="class_name", default="Policy")
    ap.add_argument("--rate", type=float, default=10.0)
    args, _ = ap.parse_known_args()                   # ignore --ros-args and friends
    iface = json.loads(args.interface)

    sys.path.insert(0, "/workspace")
    policy_cls = getattr(importlib.import_module(args.module), args.class_name)
    policy = policy_cls()
    if hasattr(policy, "reset"):
        policy.reset()

    rclpy.init()
    node = Node("policy_runner")
    latest: dict = {}
    keymap = _obs_builder(iface["observation"])

    subscribed: dict = {}
    for o in iface["observation"]:
        if o["topic"] in subscribed:
            continue
        msg_cls = get_message(o["msg_type"])
        subscribed[o["topic"]] = msg_cls
        node.create_subscription(msg_cls, o["topic"],
                                 lambda m, t=o["topic"]: latest.__setitem__(t, m), 10)

    aiface = iface["action"]
    pubs: dict = {}
    if aiface["kind"] == "velocity":
        pubs[aiface["topic"]] = node.create_publisher(Twist, aiface["topic"], 10)
    else:
        for j in aiface["joints"]:
            pubs[j["command_topic"]] = node.create_publisher(Float64, j["command_topic"], 10)

    def build_obs():
        obs = {}
        for key, (topic, fn) in keymap.items():
            if topic in latest:
                obs[key] = fn(latest[topic])
        return obs

    def tick():
        try:
            action = policy.act(build_obs())
        except Exception as e:  # noqa: BLE001 — surface policy errors, keep the node alive
            node.get_logger().error(f"policy.act raised: {e}")
            return
        for pub in plan_publications(aiface, action or {}):
            if pub["kind"] == "twist":
                t = Twist()
                f = pub["fields"]
                t.linear.x, t.linear.y, t.linear.z = f["linear_x"], f["linear_y"], f["linear_z"]
                t.angular.z = f["angular_z"]
                pubs[pub["topic"]].publish(t)
            else:
                pubs[pub["topic"]].publish(Float64(data=pub["value"]))

    node.create_timer(1.0 / max(args.rate, 1e-3), tick)
    rclpy.spin(node)


if __name__ == "__main__":
    main()
