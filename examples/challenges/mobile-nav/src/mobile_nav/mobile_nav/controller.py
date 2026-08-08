import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan


class Controller(Node):
    """Challenge starter controller — drives straight forward and ignores every sensor.

    It PASSES `drive-forward` (the warm-up) but FAILS `stop-before-obstacle`, `reach-goal`,
    and `turn-around`. Your job: rewrite it so each scenario passes. Read the scenario's
    assertions, then use `/scan` (obstacles) and `/odom` (pose) to command `/cmd_vel`.
    Run `robotbase test <scenario>` and iterate until exit 0.
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
