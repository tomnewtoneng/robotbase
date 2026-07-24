"""Record scenario metrics across the WHOLE episode and write them to a file.

Runs inside the ROS container from sim launch until it is killed. It tracks the
minimum LiDAR range and collision flag over the entire run (not just a trailing
window), so `no_collision` truly means "no collision occurred during the run".
The runtime kills it at collect time and reads the JSON it leaves behind.
"""
import argparse
import json
import math
import signal
import sys
import time

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

try:
    from ros_gz_interfaces.msg import Contacts
except ImportError:  # contact sensor optional; degrade gracefully
    Contacts = None

COLLISION_RANGE_M = 0.12
CONTACT_GAP_S = 0.5  # contact messages closer than this belong to the same episode


class Collector(Node):
    def __init__(self, output: str):
        super().__init__("metrics_collector")
        self.output = output
        self.min_range = math.inf
        self.scan_count = 0
        self.collision = 0
        self.contact_count = 0
        self._last_contact_t = -math.inf
        self.last_odom = None
        self.create_subscription(LaserScan, "/scan", self._scan, 10)
        self.create_subscription(Odometry, "/odom", self._odom, 10)
        if Contacts is not None:
            self.create_subscription(Contacts, "/bumper", self._bumper, 10)

    def _scan(self, msg: LaserScan):
        self.scan_count += 1
        for r in msg.ranges:
            if msg.range_min <= r <= msg.range_max and r < self.min_range:
                self.min_range = r
        if self.min_range < COLLISION_RANGE_M:
            self.collision = 1
        if self.scan_count % 20 == 0:
            self.write()  # periodic flush so a hard kill still leaves fresh data

    def _odom(self, msg: Odometry):
        self.last_odom = msg

    def _bumper(self, msg):
        # The contact sensor only publishes while touching, so any message with a
        # non-empty contacts array is a live collision. Count distinct episodes by
        # treating a gap since the last contact as a new one.
        if not msg.contacts:
            return
        now = time.monotonic()
        if now - self._last_contact_t > CONTACT_GAP_S:
            self.contact_count += 1
        self._last_contact_t = now

    def metrics(self) -> dict:
        if self.last_odom is not None:
            pos = self.last_odom.pose.pose.position
            tw = self.last_odom.twist.twist
            px, py, lin, ang = pos.x, pos.y, tw.linear.x, tw.angular.z
        else:
            px = py = lin = ang = 0.0
        return {
            "collision_count": self.collision,
            "contact_count": self.contact_count,
            "minimum_obstacle_distance_metres": None if math.isinf(self.min_range) else self.min_range,
            "distance_travelled_metres": math.hypot(px, py),
            "final_linear_velocity": lin,
            "final_angular_velocity": ang,
            "topic_message_counts": {"/scan": self.scan_count},
        }

    def write(self) -> None:
        try:
            with open(self.output, "w") as f:
                json.dump(self.metrics(), f)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    rclpy.init()
    node = Collector(args.output)
    node.write()  # reset the output file so a prior run's data can't be read

    def _handle(_signum, _frame):
        node.write()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.write()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
