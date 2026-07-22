# Robotbase Project Instructions

This is a ROS 2 Jazzy + Gazebo Harmonic **differential-drive robot** project that runs
headless in Docker. Your job is to implement the obstacle controller so the robot stops
before hitting obstacles — verified by simulation scenarios, not by inspection.

## Environment

The simulation runs inside a Docker container. You do **not** operate Gazebo directly.
Use the Robotbase tools — the `robotbase` CLI below, or the equivalent `robotbase` MCP
tools — to build, run scenarios, and read structured results.

## Commands (run from this directory)

Build the workspace:

    robotbase build

Run a scenario (exit code 0 = pass, 1 = fail; prints a structured JSON result):

    robotbase test <scenario-name>

List scenarios:

    robotbase test --list

Available scenarios: `drive-forward`, `stop-before-obstacle`.

## The task

The starter controller drives forward and **ignores the LiDAR**. Improve it so the robot
detects the obstacle ahead and stops before colliding, while still driving forward when
the path is clear.

- Robot type: differential drive
- Key topics: `/cmd_vel` (velocity command, `geometry_msgs/Twist`), `/scan` (LiDAR,
  `sensor_msgs/LaserScan`), `/odom` (odometry), `/tf`
- Main controller file:
  `src/warehouse_bot/warehouse_bot/obstacle_controller.py`

You do **not** need to rebuild after editing the controller (the workspace is symlink-
installed); just run the scenario again. `robotbase build` is harmless if you prefer.

## Requirements — do not claim success without evidence

Before claiming a behaviour works:

1. Run the relevant scenario with `robotbase test <name>`.
2. Read the failed assertions and the `metrics` in the JSON result.
3. Continue iterating on the controller until the scenario passes.
4. Report the final scenario metrics.

Do **not** claim success based only on reading source code. Both `drive-forward` and
`stop-before-obstacle` must pass. Prefer Robotbase tools over raw ROS/Gazebo commands.
