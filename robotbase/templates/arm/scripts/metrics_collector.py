"""Record scenario metrics across the WHOLE episode and write them to a file.

Runs inside the ROS container from sim launch until it is killed. It tracks the
minimum LiDAR range and collision/contact over the entire run (not just a trailing
window), so `no_collision`/`no_contact` truly mean "none occurred during the run".

Pose (final_x/y/yaw, distance, path) comes from the robot's GROUND-TRUTH world pose
(gz /world/<world>/dynamic_pose/info via gz-transport), NOT /odom: wheel odometry
drifts (it doesn't track a set_robot_pose teleport and integrates wheel-slip against
walls), which would score robot_reached_pose in the wrong frame. /odom is the pose
fallback and the source of the reported velocities. The runtime kills the collector
at collect time and reads the JSON it leaves behind.
"""
import argparse
import json
import math
import signal
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
CONTACT_GAP_S = 0.5   # contact messages closer than this belong to the same episode
TELEPORT_M = 0.5      # a per-update jump larger than this is a set_robot_pose teleport, not travel
MOVE_DEADBAND_M = 0.001


def _yaw(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class Collector(Node):
    def __init__(self, output: str, world: str = "", robot: str = ""):
        super().__init__("metrics_collector")
        self.output = output
        self.min_range = math.inf
        self.scan_count = 0
        self.odom_count = 0
        self.collision = 0
        self.contact_count = 0
        self._last_contact_t = -math.inf
        # pose (ground truth preferred, odom fallback) + displacement/path tracking
        self.have_gt = False
        self.px = self.py = self.yaw = 0.0
        self.lin = self.ang = 0.0
        self.path_length = 0.0
        self._anchor = None      # displacement origin (reset on a teleport)
        self._prev = None
        self.create_subscription(LaserScan, "/scan", self._scan, 10)
        self.create_subscription(Odometry, "/odom", self._odom, 10)
        if Contacts is not None:
            self.create_subscription(Contacts, "/bumper", self._bumper, 10)
        self._gz = self._start_ground_truth(world, robot)

    def _start_ground_truth(self, world, robot):
        if not world or not robot:
            return None
        try:
            from gz.transport13 import Node as GzNode
            from gz.msgs10.pose_v_pb2 import Pose_V
        except Exception:
            return None

        def on_poses(msg):
            for p in msg.pose:
                if p.name == robot:
                    if not self.have_gt:          # first ground-truth fix: start path fresh
                        self.have_gt = True
                        self._anchor = self._prev = (p.position.x, p.position.y)
                        self.path_length = 0.0
                    self._advance(p.position.x, p.position.y)
                    self.px, self.py, self.yaw = p.position.x, p.position.y, _yaw(p.orientation)
                    return

        gz = GzNode()
        return gz if gz.subscribe(Pose_V, f"/world/{world}/dynamic_pose/info", on_poses) else None

    def _advance(self, x, y):
        if self._prev is not None:
            step = math.hypot(x - self._prev[0], y - self._prev[1])
            if step > TELEPORT_M:
                self._anchor = (x, y)             # teleport: reset origin, don't count the jump
            elif step > MOVE_DEADBAND_M:
                self.path_length += step
        if self._anchor is None:
            self._anchor = (x, y)
        self._prev = (x, y)

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
        self.odom_count += 1
        tw = msg.twist.twist
        self.lin, self.ang = tw.linear.x, tw.angular.z
        if not self.have_gt:                       # fallback pose/path until ground truth arrives
            p = msg.pose.pose.position
            self._advance(p.x, p.y)
            self.px, self.py, self.yaw = p.x, p.y, _yaw(msg.pose.pose.orientation)

    def _bumper(self, msg):
        # The contact sensor only publishes while touching, so any message with a non-empty
        # contacts array is a live collision. Count distinct episodes by gap since the last contact.
        if not msg.contacts:
            return
        now = time.monotonic()
        if now - self._last_contact_t > CONTACT_GAP_S:
            self.contact_count += 1
        self._last_contact_t = now

    def metrics(self) -> dict:
        ax, ay = self._anchor if self._anchor else (self.px, self.py)
        return {
            "collision_count": self.collision,
            "contact_count": self.contact_count,
            "minimum_obstacle_distance_metres": None if math.isinf(self.min_range) else self.min_range,
            "distance_travelled_metres": math.hypot(self.px - ax, self.py - ay),
            "path_length_metres": self.path_length,
            "final_x": self.px,
            "final_y": self.py,
            "final_yaw": self.yaw,
            "final_linear_velocity": self.lin,
            "final_angular_velocity": self.ang,
            "pose_source": "ground_truth" if self.have_gt else "odom",
            "topic_message_counts": {"/scan": self.scan_count, "/odom": self.odom_count},
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
    ap.add_argument("--world", default="")
    ap.add_argument("--robot", default="")
    args = ap.parse_args()

    rclpy.init()
    node = Collector(args.output, args.world, args.robot)
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
