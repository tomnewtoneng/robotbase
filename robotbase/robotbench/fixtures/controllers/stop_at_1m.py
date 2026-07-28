"""Provided RobotBench controller (IMMUTABLE to the agent): drive forward, stop within 1 m.

Subscribes /scan (LaserScan), publishes /cmd_vel (Twist). This single file is copied
byte-identically into both arms' scaffolds so the authoring task — not the control logic — is
what varies. The pure `desired_twist` helper is unit-tested without ROS.
"""
import math


def desired_twist(ranges, stop_range_m: float = 1.0, speed: float = 0.3):
    """Forward at `speed` until something in the forward third of the scan is within
    `stop_range_m`, then stop. Non-finite / non-positive returns are ignored."""
    finite = [r for r in ranges if r is not None and math.isfinite(r) and r > 0.0]
    ahead = finite[len(finite) // 3: 2 * len(finite) // 3] if finite else []
    if ahead and min(ahead) <= stop_range_m:
        return 0.0, 0.0
    return speed, 0.0


def main():  # pragma: no cover - live ROS entrypoint
    import rclpy
    from rclpy.node import Node
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import LaserScan
    rclpy.init()
    node = Node("stop_at_1m")
    pub = node.create_publisher(Twist, "/cmd_vel", 10)

    def on_scan(msg):
        lin, ang = desired_twist(list(msg.ranges))
        t = Twist()
        t.linear.x = lin
        t.angular.z = ang
        pub.publish(t)

    node.create_subscription(LaserScan, "/scan", on_scan, 10)
    rclpy.spin(node)


if __name__ == "__main__":
    main()
