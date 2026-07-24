import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64


class Controller(Node):
    """Starter arm controller — deliberately incomplete.

    It sets up the joint-command publishers but never commands a target, so the arm just
    droops under gravity and fails any reach scenario. Rewrite it to command the joints to
    the target configuration the scenario asks for: publish the target angle (radians) on
    `/shoulder_cmd` and `/elbow_cmd` (`std_msgs/Float64`), and keep publishing so the
    position controllers hold the pose. Read the current angles on `/joint_states`.
    """

    def __init__(self):
        super().__init__("controller")
        self.shoulder = self.create_publisher(Float64, "/shoulder_cmd", 10)
        self.elbow = self.create_publisher(Float64, "/elbow_cmd", 10)
        self.create_timer(0.1, self._tick)

    def _tick(self):
        # Starter bug: no target is ever commanded, so the arm never moves to the goal.
        pass


def main():
    rclpy.init()
    node = Controller()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
