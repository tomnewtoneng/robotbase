"""Record drone metrics across the WHOLE episode and write them to a file.

Runs inside the ROS container from sim launch until it is killed. Tracks the drone's final
3D pose (x, y, z, yaw) from /odom — the basis for a 3D `robot_reached_pose` assertion. The
runtime kills it at collect time and reads the JSON it leaves behind.
"""
import argparse
import json
import math
import signal

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node


class Collector(Node):
    def __init__(self, output: str):
        super().__init__("metrics_collector")
        self.output = output
        self.last_odom = None
        self.odom_count = 0
        self.path_length = 0.0
        self._prev = None
        self.create_subscription(Odometry, "/odom", self._odom, 10)

    def _odom(self, msg: Odometry):
        self.last_odom = msg
        self.odom_count += 1
        p = msg.pose.pose.position
        if self._prev is not None:
            step = math.sqrt((p.x - self._prev[0]) ** 2 + (p.y - self._prev[1]) ** 2
                             + (p.z - self._prev[2]) ** 2)
            if step > 0.001:
                self.path_length += step
        self._prev = (p.x, p.y, p.z)
        if self.odom_count % 30 == 0:
            self.write()

    def metrics(self) -> dict:
        px = py = pz = yaw = lin = ang = 0.0
        if self.last_odom is not None:
            pos = self.last_odom.pose.pose.position
            ori = self.last_odom.pose.pose.orientation
            tw = self.last_odom.twist.twist
            px, py, pz, lin, ang = pos.x, pos.y, pos.z, tw.linear.x, tw.angular.z
            yaw = math.atan2(2.0 * (ori.w * ori.z + ori.x * ori.y),
                             1.0 - 2.0 * (ori.y * ori.y + ori.z * ori.z))
        return {
            "distance_travelled_metres": math.sqrt(px * px + py * py + pz * pz),
            "path_length_metres": self.path_length,
            "final_x": px, "final_y": py, "final_z": pz, "final_yaw": yaw,
            "final_linear_velocity": lin, "final_angular_velocity": ang,
            "topic_message_counts": {"/odom": self.odom_count},
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
    node.write()

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
