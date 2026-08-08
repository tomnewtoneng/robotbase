"""Derive a robot's policy interface (observation topics/keys + action interface) from the
compiled project manifest. Pure host-side; the single source of truth shared by `describe`
(so an agent sees the contract) and the container-side policy runner (so it wires the same
topics). No drift: both read this."""
from __future__ import annotations

# sensor manifest key -> (obs key, ROS msg type). odometry yields two obs keys.
_SENSOR_OBS = {
    "lidar": [("scan", "sensor_msgs/msg/LaserScan")],
    "odometry": [("pose", "nav_msgs/msg/Odometry"), ("velocity", "nav_msgs/msg/Odometry")],
    "imu": [("imu", "sensor_msgs/msg/Imu")],
    "camera": [("image", "sensor_msgs/msg/Image")],
    "depth": [("depth", "sensor_msgs/msg/Image")],
}
_VELOCITY_KEYS = ["linear_x", "linear_y", "linear_z", "angular_z"]
DEFAULT_RATE_HZ = 10.0


def policy_interface(manifest: dict) -> dict:
    observation: list[dict] = []
    for name, cfg in (manifest.get("sensors") or {}).items():
        if not (cfg or {}).get("enabled", True):
            continue
        topic = (cfg or {}).get("topic")
        for key, msg_type in _SENSOR_OBS.get(name, []):
            observation.append({"key": key, "topic": topic, "msg_type": msg_type})

    joints_block = manifest.get("joints") or {}
    if joints_block:
        state_topic = joints_block.get("state_topic", "/joint_states")
        observation.append({"key": "joints", "topic": state_topic,
                            "msg_type": "sensor_msgs/msg/JointState"})
        action = {"kind": "joints", "joints": [
            {"name": cfg["joint"], "command_topic": cfg["command_topic"]}
            for alias, cfg in joints_block.items() if isinstance(cfg, dict) and "joint" in cfg
        ]}
    else:
        vt = (manifest.get("control") or {}).get("velocity_topic", "/cmd_vel")
        action = {"kind": "velocity", "topic": vt, "keys": list(_VELOCITY_KEYS)}

    return {"observation": observation, "action": action, "control_rate_hz": DEFAULT_RATE_HZ}
