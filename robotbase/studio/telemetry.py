"""Self-contained telemetry node — runs INSIDE the ROS container (no `robotbase` import there).
Writes the robot's latest pose + scan + joints to the mounted /workspace/.robotbase/telemetry.jsonl
on a **wall-clock** 10 Hz timer (a heartbeat), so Studio (host) can (a) render the pose live and
(b) detect the node's liveness by the file's freshness — Robotbase restarts the container on every
scenario reset, so Studio's supervisor relaunches this node when the file goes stale.

Pose source: the robot's **ground-truth world pose** from gz (`/world/<world>/dynamic_pose/info`),
NOT `/odom`. Wheel odometry drifts badly here — it doesn't track the `set_robot_pose` teleport and
integrates wheel-slip while the robot is against a wall — so drawing the marker at /odom put the
robot in the wrong "room" with the lidar of its real surroundings around it. `/odom` remains a
fallback if gz-transport isn't available.

Launched by runtime.start_telemetry:  python3 telemetry.py --world <name> --robot <model>
(No use_sim_time: the write timer must be wall-clock so it keeps ticking when sim time is paused.)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time

OUT = "/workspace/.robotbase/telemetry.jsonl"


def yaw_from_quat(x, y, z, w):
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _start_ground_truth(world, robot, latest, have_gt):
    """Subscribe to gz ground-truth model poses; update `latest` with the robot's world pose.
    Returns the gz node (kept alive) or None if gz-transport isn't importable."""
    if not world or not robot:
        return None
    try:  # version-pinned to the sim's gz release (Harmonic/jazzy = transport13/msgs10)
        from gz.transport13 import Node as GzNode
        from gz.msgs10.pose_v_pb2 import Pose_V
    except Exception:
        return None

    def on_poses(msg):
        for p in msg.pose:
            if p.name == robot:
                q = p.orientation
                latest.update({"t": time.time(), "x": p.position.x, "y": p.position.y,
                               "z": p.position.z, "yaw": yaw_from_quat(q.x, q.y, q.z, q.w)})
                have_gt["v"] = True
                return

    gz = GzNode()
    return gz if gz.subscribe(Pose_V, f"/world/{world}/dynamic_pose/info", on_poses) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", default="")
    ap.add_argument("--robot", default="")
    args = ap.parse_args()

    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from sensor_msgs.msg import JointState, LaserScan

    rclpy.init()
    node = Node("studio_telemetry")
    latest = {"t": time.time()}
    have_gt = {"v": False}

    gz = _start_ground_truth(args.world, args.robot, latest, have_gt)  # noqa: F841 (kept alive)

    def on_odom(msg):
        if have_gt["v"]:
            return                                  # ground truth is authoritative once it arrives
        p = msg.pose.pose.position
        o = msg.pose.pose.orientation
        latest.update({"t": time.time(), "x": p.x, "y": p.y, "z": p.z,
                       "yaw": yaw_from_quat(o.x, o.y, o.z, o.w)})

    def on_joints(msg):
        latest["joints"] = {n: p for n, p in zip(msg.name, msg.position)}

    def on_scan(msg):
        n = len(msg.ranges)
        stride = max(1, (n + 199) // 200)          # cap ~200 rays
        latest["scan"] = {
            "ranges": [None if not (msg.range_min <= r <= msg.range_max) else round(r, 3)
                       for r in msg.ranges[::stride]],
            "angle_min": msg.angle_min,
            "angle_increment": msg.angle_increment * stride,
            "range_max": msg.range_max,
        }

    def write():
        latest["t"] = time.time()          # heartbeat even when the pose is quiet
        tmp = OUT + ".tmp"
        with open(tmp, "w") as f:
            f.write(json.dumps(latest))
        os.replace(tmp, OUT)               # atomic — no partial reads on the host

    node.create_subscription(Odometry, "/odom", on_odom, 10)
    node.create_subscription(JointState, "/joint_states", on_joints, 10)
    node.create_subscription(LaserScan, "/scan", on_scan, 10)
    node.create_timer(0.1, write)          # 10 Hz wall-clock heartbeat + latest pose/joints/scan
    rclpy.spin(node)


if __name__ == "__main__":
    main()
