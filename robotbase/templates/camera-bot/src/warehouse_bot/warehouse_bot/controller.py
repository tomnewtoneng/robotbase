import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class Controller(Node):
    """A minimal working controller: it drives the robot straight forward, which passes the
    bundled `drive-forward` scenario.

    This is a starting point, not a finished behaviour — it ignores the robot's sensors.
    Replace it with your own logic: read the scenario's assertions, subscribe to the sensors
    you need (`/scan` for obstacles, `/image` for the camera, `/odom` for pose), and command
    `/cmd_vel` accordingly. See the worked control challenges in the repo's `examples/challenges/`.
    """

    def __init__(self):
        super().__init__("controller")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_timer(0.1, self._tick)

    def _tick(self):
        cmd = Twist()
        cmd.linear.x = 0.3
        self.pub.publish(cmd)


def main():
    rclpy.init()
    node = Controller()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
