import os

import yaml

from robotbase.generator import template_dir
from robotbase.policy_interface import policy_interface


def _manifest(tmpl):
    with open(os.path.join(template_dir(tmpl), "robotbase.yaml")) as f:
        return yaml.safe_load(f)


def test_velocity_robot_interface():
    pi = policy_interface(_manifest("differential-drive"))
    assert pi["action"] == {"kind": "velocity", "topic": "/cmd_vel",
                            "keys": ["linear_x", "linear_y", "linear_z", "angular_z"]}
    obs = {o["key"]: o for o in pi["observation"]}
    assert obs["scan"]["topic"] == "/scan" and obs["scan"]["msg_type"] == "sensor_msgs/msg/LaserScan"
    assert obs["pose"]["topic"] == "/odom" and obs["velocity"]["topic"] == "/odom"
    assert pi["control_rate_hz"] == 10.0


def test_arm_interface():
    pi = policy_interface(_manifest("arm"))
    assert pi["action"]["kind"] == "joints"
    names = {j["name"]: j["command_topic"] for j in pi["action"]["joints"]}
    assert names == {"shoulder_joint": "/shoulder_cmd", "elbow_joint": "/elbow_cmd"}
    obs = {o["key"]: o for o in pi["observation"]}
    assert obs["joints"]["topic"] == "/joint_states" and obs["joints"]["msg_type"] == "sensor_msgs/msg/JointState"


def test_camera_robot_has_image_obs():
    pi = policy_interface(_manifest("camera-bot"))
    obs = {o["key"] for o in pi["observation"]}
    assert {"scan", "pose", "velocity", "image"} <= obs
