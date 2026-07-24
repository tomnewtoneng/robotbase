import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan


class Controller(Node):
    """Starter controller — deliberately incomplete.

    It just drives straight forward and ignores every sensor, so it fails all
    scenarios. Rewrite it to satisfy the scenario you're solving: read that
    scenario's assertions, then use the robot's sensors (`/scan` for obstacles,
    `/odom` for pose) to command `/cmd_vel` accordingly.
    """

    def __init__(self):
        super().__init__("controller")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        # Starter subscribes to /scan but ignores it; add /odom etc. as your task needs.
        self.create_subscription(LaserScan, "/scan", self._on_scan, 10)
        self.create_timer(0.1, self._tick)

    def _on_scan(self, msg: LaserScan):
        # Starter bug: sensor data is ignored entirely.
        pass

    def _tick(self):
        cmd = Twist()
        cmd.linear.x = 0.3  # always forward, never reacts
        self.pub.publish(cmd)


def main():
    rclpy.init()
    node = Controller()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
