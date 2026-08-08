import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64


class Controller(Node):
    """A minimal working controller: it commands the 2-joint arm to a fixed configuration and
    holds it (shoulder = 1.0 rad, elbow = -1.4 rad), which passes the bundled
    `reach-configuration` scenario.

    This is a starting point, not a finished behaviour. Replace it with your own logic: read the
    current angles on `/joint_states` and command the joint targets your task needs on
    `/shoulder_cmd` and `/elbow_cmd` (`std_msgs/Float64`), publishing continuously so the
    position controllers hold the pose.
    """

    def __init__(self):
        super().__init__("controller")
        self.shoulder = self.create_publisher(Float64, "/shoulder_cmd", 10)
        self.elbow = self.create_publisher(Float64, "/elbow_cmd", 10)
        self.create_timer(0.1, self._tick)

    def _tick(self):
        self.shoulder.publish(Float64(data=1.0))
        self.elbow.publish(Float64(data=-1.4))


def main():
    rclpy.init()
    node = Controller()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
