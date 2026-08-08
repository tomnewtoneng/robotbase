# Robotbase Project Instructions

This is a Robotbase **quadrotor drone** project — a ROS 2 Jazzy + Gazebo Harmonic stack that runs
headless in Docker. You build and verify robots *declaratively*: everything here is yours to change
— the drone and its sensors (`robot.yaml`), the world (`world.yaml`), the control config, and the
test scenarios — plus the control logic you implement. You edit, compile, and run, verifying by the
structured result, never by inspection.

This project ships a working drone, a scenario, and a **starter controller you implement**. Run
`robotbase describe` for ground truth and `robotbase schema` for the full authoring format (robot /
world / **scenario**). When a task is about a specific scenario, **read its YAML first** for its
target and tolerance.

## Environment

The simulation runs inside a Docker container. You do **not** operate Gazebo directly. Use
the Robotbase tools — the `robotbase` CLI below, or the equivalent MCP tools.

## Commands (run from this directory)

    robotbase describe              # robot facts, world, scenarios
    robotbase build                 # build the workspace
    robotbase test <scenario-name>  # run a scenario (exit 0 = pass; JSON result)
    robotbase test --list           # list scenarios
    robotbase diagnose              # plain-language why the last run failed

Available scenarios:

- `reach-position` — fly to a target 3D position and hover there.

## The drone

Flight is **kinematic velocity control**: publish a 3D velocity on `/cmd_vel`
(`geometry_msgs/Twist` — `linear.x`, `linear.y`, `linear.z`, `angular.z`) and the body tracks
it. Command `linear.z > 0` to climb, `linear.z = 0` to hover. Read the current pose (including
**altitude, `z`**) from `/odom` (`nav_msgs/Odometry`), and attitude from `/imu`. The odom
frame starts at the drone's launch pose (≈ 0).

The starter controller (`src/drone_navigate/drone_navigate/controller.py`) never commands a
velocity, so the drone never leaves the ground and fails. Rewrite it to fly to the target:
read `/odom`, compute the 3D position error to the goal, and command a proportional `/cmd_vel`
toward it — easing the velocity toward zero as you arrive so it hovers at the target.

You do **not** need to rebuild after editing the controller (symlink-installed); just re-run.

## Requirements — do not claim success without evidence

1. Run the scenario with `robotbase test <name>` and read the `final_x/y/z` metrics and the
   assertion result; use `robotbase diagnose` to understand a failure.
2. Iterate until the scenario passes (exit 0, all assertions true).
3. Report the final metrics.

Do **not** claim success from reading source code — the scenario must actually pass. Prefer
Robotbase tools over raw ROS/Gazebo commands.
