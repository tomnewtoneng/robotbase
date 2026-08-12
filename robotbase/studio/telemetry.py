"""Self-contained telemetry node — runs INSIDE the ROS container (no `robotbase` import there).
Subscribes to /odom and writes the latest pose atomically to the mounted
/workspace/.robotbase/telemetry.jsonl (~10 Hz), so Studio (host) can read it without a port.
Launched by runtime.start_telemetry via:  python3 /workspace/.robotbase/telemetry.py --ros-args -p use_sim_time:=true
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
    state = {"last": 0.0}

    def on_odom(msg):
        now = time.monotonic()
        if now - state["last"] < 0.1:      # throttle ~10 Hz
            return
        state["last"] = now
        p = msg.pose.pose.position
        o = msg.pose.pose.orientation
        line = json.dumps({"t": now, "x": p.x, "y": p.y, "z": p.z,
                           "yaw": yaw_from_quat(o.x, o.y, o.z, o.w)})
        tmp = OUT + ".tmp"
        with open(tmp, "w") as f:
            f.write(line)
        os.replace(tmp, OUT)               # atomic — no partial reads on the host

    node.create_subscription(Odometry, "/odom", on_odom, 10)
    rclpy.spin(node)


if __name__ == "__main__":
    main()
