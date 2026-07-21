import sys
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class ScanCheck(Node):
    def __init__(self):
        super().__init__("scan_check")
        self.ok = False
        self.create_subscription(LaserScan, "/scan", self._cb, 10)

    def _cb(self, msg: LaserScan):
        finite = [r for r in msg.ranges if msg.range_min <= r <= msg.range_max]
        if len(finite) >= 10:
            self.get_logger().info(
                f"/scan OK: {len(finite)} finite ranges, min={min(finite):.2f}"
            )
            self.ok = True


def main():
    rclpy.init()
    node = ScanCheck()
    end = node.get_clock().now().nanoseconds + 15 * 1_000_000_000
    while rclpy.ok() and not node.ok and node.get_clock().now().nanoseconds < end:
        rclpy.spin_once(node, timeout_sec=0.5)
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if node.ok else 1)


if __name__ == "__main__":
    main()
