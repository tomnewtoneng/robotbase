import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry


class Controller(Node):
    """A minimal working controller: it takes off and hovers about 1.5 m above the start,
    which passes the bundled `take-off` scenario. It's a simple proportional controller on the
    pose from `/odom` — command velocity toward the target, easing to zero as it arrives.

    This is a starting point, not a finished behaviour. Replace it with your own logic: read the
    pose from `/odom` and command a 3-D velocity on `/cmd_vel` (`geometry_msgs/Twist`:
    `linear.x/y/z`) toward whatever target your task needs. See `examples/challenges/` for a
    3-D navigation challenge.
    """

    TARGET = (0.0, 0.0, 1.5)
    KP = 0.9
    VMAX = 1.0

    def __init__(self):
        super().__init__("controller")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Odometry, "/odom", self._on_odom, 10)
        self.create_timer(0.1, self._tick)
        self.pose = None

    def _on_odom(self, msg: Odometry):
        self.pose = msg.pose.pose.position

    def _tick(self):
        cmd = Twist()
        if self.pose is not None:
            tx, ty, tz = self.TARGET
            cmd.linear.x = self._clamp(self.KP * (tx - self.pose.x))
            cmd.linear.y = self._clamp(self.KP * (ty - self.pose.y))
            cmd.linear.z = self._clamp(self.KP * (tz - self.pose.z))
        self.pub.publish(cmd)

    def _clamp(self, v: float) -> float:
        return max(-self.VMAX, min(self.VMAX, v))


def main():
    rclpy.init()
    node = Controller()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
