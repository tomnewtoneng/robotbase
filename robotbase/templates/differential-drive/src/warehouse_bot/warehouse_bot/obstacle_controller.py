import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan


class ObstacleController(Node):
    """Starter controller.

    The initial implementation drives forward without reacting correctly to
    obstacles. The coding agent is expected to improve it so the robot stops
    before hitting the box.
    """

    def __init__(self):
        super().__init__("obstacle_controller")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(LaserScan, "/scan", self._on_scan, 10)
        self.create_timer(0.1, self._tick)

    def _on_scan(self, msg: LaserScan):
        # Starter bug: LiDAR data is ignored entirely.
        pass

    def _tick(self):
        cmd = Twist()
        cmd.linear.x = 0.3  # always forward, never stops
        self.pub.publish(cmd)


def main():
    rclpy.init()
    node = ObstacleController()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
