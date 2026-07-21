"""Sample /scan and /odom for a window and emit scenario metrics as JSON.

Runs inside the ROS container (needs rclpy). The runtime module invokes this
and parses the final JSON line into a robotbase Metrics model.
"""
import argparse
import json
import math

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class Collector(Node):
    def __init__(self):
        super().__init__("metrics_collector")
        self.min_range = math.inf
        self.scan_count = 0
        self.last_odom = None
        self.create_subscription(LaserScan, "/scan", self._scan, 10)
        self.create_subscription(Odometry, "/odom", self._odom, 10)

    def _scan(self, msg: LaserScan):
        self.scan_count += 1
        for r in msg.ranges:
            if msg.range_min <= r <= msg.range_max and r < self.min_range:
                self.min_range = r

    def _odom(self, msg: Odometry):
        self.last_odom = msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=3.0)
    args = ap.parse_args()

    rclpy.init()
    node = Collector()
    end = node.get_clock().now().nanoseconds + int(args.duration * 1e9)
    while rclpy.ok() and node.get_clock().now().nanoseconds < end:
        rclpy.spin_once(node, timeout_sec=0.2)

    if node.last_odom is not None:
        pos = node.last_odom.pose.pose.position
        tw = node.last_odom.twist.twist
        px, py, lin, ang = pos.x, pos.y, tw.linear.x, tw.angular.z
    else:
        px = py = lin = ang = 0.0

    min_r = None if math.isinf(node.min_range) else node.min_range
    metrics = {
        "collision_count": 1 if (min_r is not None and min_r < 0.12) else 0,
        "minimum_obstacle_distance_metres": min_r,
        "distance_travelled_metres": math.hypot(px, py),
        "final_linear_velocity": lin,
        "final_angular_velocity": ang,
        "topic_message_counts": {"/scan": node.scan_count},
    }
    print(json.dumps(metrics))
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
