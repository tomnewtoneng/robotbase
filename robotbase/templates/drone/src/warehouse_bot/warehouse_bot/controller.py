import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


class Controller(Node):
    """Starter drone controller — deliberately incomplete.

    It sets up the /cmd_vel publisher and subscribes to /odom, but never commands a velocity,
    so the drone just sits on the ground and fails any reach scenario. Rewrite it to fly to
    the target: read the current pose from /odom and publish a 3D velocity on /cmd_vel
    (`geometry_msgs/Twist`: `linear.x/y/z`) toward the goal — command `linear.z > 0` to climb
    — easing toward zero as you arrive so the drone hovers at the target.
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
