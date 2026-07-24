"""Record arm metrics across the WHOLE episode and write them to a file.

Runs inside the ROS container from sim launch until it is killed. For the arm it tracks
the latest joint positions from /joint_states (the basis for the joint_positions_reached
assertion). The runtime kills it at collect time and reads the JSON it leaves behind.
"""
import argparse
import json
import signal

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class Collector(Node):
    def __init__(self, output: str):
        super().__init__("metrics_collector")
        self.output = output
        self.joint_positions: dict[str, float] = {}
        self.joint_velocities: dict[str, float] = {}
        self.js_count = 0
        self.create_subscription(JointState, "/joint_states", self._joints, 10)

    def _joints(self, msg: JointState):
        self.js_count += 1
        vels = msg.velocity if len(msg.velocity) == len(msg.name) else [0.0] * len(msg.name)
        for name, pos, vel in zip(msg.name, msg.position, vels):
            if name == "fixed_base":
                continue  # not an actuated joint
            self.joint_positions[name] = pos
            self.joint_velocities[name] = vel
        if self.js_count % 20 == 0:
            self.write()  # periodic flush so a hard kill still leaves fresh data

    def metrics(self) -> dict:
        # joint_velocities are the latest sample: near-zero means the arm has settled and
        # is holding the pose (rather than being caught mid-motion at capture time).
        return {
            "joint_positions": {k: round(v, 4) for k, v in self.joint_positions.items()},
            "joint_velocities": {k: round(v, 4) for k, v in self.joint_velocities.items()},
            "topic_message_counts": {"/joint_states": self.js_count},
        }

    def write(self) -> None:
        try:
            with open(self.output, "w") as f:
                json.dump(self.metrics(), f)
        except OSError:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    rclpy.init()
    node = Collector(args.output)
    node.write()  # reset the output file so a prior run's data can't be read

    def _handle(_signum, _frame):
        node.write()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.write()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
