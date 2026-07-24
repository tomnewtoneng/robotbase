# Robotbase Project Instructions

This is a ROS 2 Jazzy + Gazebo Harmonic **differential-drive robot** project that runs
headless in Docker. Your job is to implement the robot's controller so that the
**simulation scenario you're asked to satisfy passes** — verified by running it, not by
inspection. Different scenarios require different behaviour, so **read the scenario's YAML
first** to learn what it checks; don't assume the task from the file names.

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

Available scenarios (each `.yaml` in `simulation/scenarios/` defines its own setup and
**assertions** — read the one you're solving):

- `drive-forward` — drive forward a minimum distance.
- `stop-before-obstacle` — a box is spawned ahead; stop before hitting it (uses `/scan`).
- `reach-goal` — drive to a target **pose** (off to one side) and stop there; needs
  `/odom` heading control, not obstacle avoidance.
- `turn-around` — a wall blocks the direct path to a goal beyond it; go around it
  (combine `/scan` avoidance with `/odom` goal-seeking) without colliding.

## The controller

The starter controller (`src/warehouse_bot/warehouse_bot/obstacle_controller.py`) just
drives straight forward and ignores its sensors — so it fails every scenario. Rewrite it to
satisfy whichever scenario you're working on. Read that scenario's assertions to see exactly
what "pass" means (e.g. `robot_reached_pose` wants a final position near a target;
`no_contact`/`no_collision` want you not to hit anything).

- Robot type: differential drive
- Key topics: `/cmd_vel` (velocity command out, `geometry_msgs/Twist`: `linear.x` forward,
  `angular.z` turn), `/scan` (LiDAR, `sensor_msgs/LaserScan`), `/image` (forward camera,
  `sensor_msgs/Image`), `/odom` (pose + velocity, `nav_msgs/Odometry`), `/bumper` (contact
  sensor, `ros_gz_interfaces/Contacts` — fires on a real collision), `/tf`
- **`/odom` is wheel odometry (dead-reckoned):** it drifts when the wheels slip, so a robot
  stalled against something keeps reporting an advancing position even though it isn't
  moving. If `final_x`/`distance_travelled` look impossibly large, the robot is stuck —
  cross-check `contact_count`/`no_contact`.
- **For exact geometry, read the source of truth — don't assume, and don't trust numbers
  restated in prose (this file deliberately doesn't hardcode them, so they can't drift):**
  the robot is defined in its URDF (`src/warehouse_bot_description/urdf/warehouse_bot.urdf.xacro`)
  and the world — arena walls, obstacles, goal markers — in
  `src/warehouse_bot_description/worlds/warehouse.sdf`. The starting pose is whatever the
  scenario's `setup.robot.pose` specifies.

You do **not** need to rebuild after editing the controller (the workspace is symlink-
installed); just run the scenario again. `robotbase build` is harmless if you prefer.

## Inspecting a failed run

Every scenario run is recorded to an MCAP episode you can interrogate — use it to
understand *why* a run failed instead of guessing:

    robotbase episode summary            # topics, message counts, duration (latest run)
    robotbase episode events             # derived timeline, e.g. the collision timestamp
    robotbase episode query --topic /scan --around <t> --window 1.5
    robotbase episode query --topic /cmd_vel --around <t>

Typical loop: `episode events` gives you the collision time `t`; then `episode query`
`/scan` and `/cmd_vel` around `t` shows what the LiDAR saw and what your controller
commanded at that moment. For a navigation task, `episode query --topic /odom` shows the
robot's trajectory over the run. Output is bounded and downsampled — safe to read directly.
(Tip: `episode summary`/`events`/`query` print JSON on stdout and a next-step hint on
stderr — capture stdout alone, e.g. `2>/dev/null`, if you're parsing the JSON.)

## Requirements — do not claim success without evidence

Before claiming a behaviour works:

1. Run the relevant scenario with `robotbase test <name>`.
2. Read the failed assertions and the `metrics` in the JSON result.
3. When a run fails, inspect the episode (above) to see what happened at the failure.
4. Continue iterating on the controller until the scenario passes.
5. Report the final scenario metrics.

Do **not** claim success based only on reading source code — the scenario you're solving
must actually pass (exit 0, all assertions true). Prefer Robotbase tools over raw ROS/Gazebo
commands.
