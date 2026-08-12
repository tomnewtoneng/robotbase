"""Self-contained telemetry node — runs INSIDE the ROS container (no `robotbase` import there).
Subscribes to /odom and writes the latest pose to the mounted /workspace/.robotbase/telemetry.jsonl
on a **wall-clock** 10 Hz timer (a heartbeat), so Studio (host) can (a) render the pose live and
(b) detect the node's liveness by the file's freshness — Robotbase restarts the container on every
scenario reset, so Studio's supervisor relaunches this node when the file goes stale.

Launched by runtime.start_telemetry:  python3 /workspace/.robotbase/telemetry.py
(No use_sim_time: the write timer must be wall-clock so it keeps ticking when sim time is paused.)
"""
from __future__ import annotations

import json
import math
import os
import time

OUT = "/workspace/.robotbase/telemetry.jsonl"


def yaw_from_quat(x, y, z, w):
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def main():
    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.node import Node

    rclpy.init()
    node = Node("studio_telemetry")
    latest = {"t": time.time()}

    def on_odom(msg):
        p = msg.pose.pose.position
        o = msg.pose.pose.orientation
        latest.update({"t": time.time(), "x": p.x, "y": p.y, "z": p.z,
                       "yaw": yaw_from_quat(o.x, o.y, o.z, o.w)})

    def write():
        latest["t"] = time.time()          # heartbeat even when /odom is quiet
        tmp = OUT + ".tmp"
        with open(tmp, "w") as f:
            f.write(json.dumps(latest))
        os.replace(tmp, OUT)               # atomic — no partial reads on the host

    node.create_subscription(Odometry, "/odom", on_odom, 10)
    node.create_timer(0.1, write)          # 10 Hz wall-clock heartbeat + latest pose
    rclpy.spin(node)


if __name__ == "__main__":
    main()
