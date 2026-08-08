import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


class Controller(Node):
    """Challenge starter controller — commands nothing, so the drone never leaves the ground
    and FAILS `reach-position`.

    Your job: fly to the target (2, 0, 2) and hover. Read the pose from `/odom` and command a
    3-D velocity on `/cmd_vel` (`linear.x/y/z`), easing to zero as you arrive. Run
    `robotbase test reach-position` and iterate until exit 0.
    """

    def __init__(self):
        super().__init__("controller")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.create_timer(0.1, self._tick)
        self.pose = None

    def _on_odom(self, msg: Odometry):
        self.pose = msg.pose.pose.position

    def _tick(self):
        # Starter bug: no velocity is ever commanded, so the drone never takes off.
        self.pub.publish(Twist())


def main():
    rclpy.init()
    node = Controller()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
