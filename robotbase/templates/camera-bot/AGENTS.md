# Robotbase Project Instructions

This is a Robotbase **camera-bot** project (a differential-drive base with a forward + depth camera)
— a ROS 2 Jazzy + Gazebo Harmonic stack that runs headless in Docker. You build and verify robots
*declaratively*: everything here is yours to change — the robot and its sensors (`robot.yaml`), the
world (`world.yaml`), the control config, and the test scenarios — plus the control logic you
implement. You edit, compile, and run, verifying by the structured result, never by inspection.

This project ships a working differential-drive robot with a LiDAR and a camera (`/image`), one
**smoke-test scenario** (`drive-forward`), and a **minimal working controller** that passes it.
Everything here is yours to change. Run `robotbase describe` for ground truth and `robotbase schema`
for the
full authoring format (robot / world / **scenario**). When a task is about a specific scenario,
**read its YAML first** — it declares exactly what it checks; don't assume the task from file names.

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

This project ships one scenario (`robotbase test --list` to confirm):

- `drive-forward` — drive forward a minimum distance.

Add your own with `robotbase scenario add <name>`. Worked, harder challenges (stop before an
obstacle, reach a goal pose, navigate around a wall) live in the repo's `examples/challenges/`.

## The controller

Your control *algorithm* lives in `controller.py` (below) — that's always yours to write. The drive
controller's *config* is declarative: `robot.yaml`'s `control: {base: {odom_publish_frequency, ...}}`
tunes it, and wheel geometry stays in `drive:` (you rarely need this).

The starter controller (`src/warehouse_bot/warehouse_bot/controller.py`) drives straight
forward — enough to pass `drive-forward`. It ignores the sensors; rewrite it to add real
behaviour, reading the assertions of whatever scenario you're solving (worked control challenges
live in the repo's `examples/challenges/`). Read that scenario's assertions to see exactly
what "pass" means (e.g. `robot_reached_pose` wants a final position near a target;
`no_contact`/`no_collision` want you not to hit anything).

You can also drive a scenario with a **Python policy** instead of the ROS controller — run
`robotbase policy new`, then set the scenario's action to `{type: run_policy, module: policy}`.
See `robotbase describe` → `policy_interface` for this robot's obs/action keys.

To measure robustness statistically, run `robotbase eval <scenario> --trials N` — a success-rate
with a confidence interval and a persisted report (a single `robotbase test` is one trial).

- Robot type: differential drive
- Key topics: `/cmd_vel` (velocity command out, `geometry_msgs/Twist`: `linear.x` forward,
  `angular.z` turn), `/scan` (LiDAR, `sensor_msgs/LaserScan`), `/image` (forward camera,
  `sensor_msgs/Image`), `/depth` (depth image, `sensor_msgs/Image` 32FC1) + `/depth/points`
  (point cloud, `sensor_msgs/PointCloud2`), `/imu`, `/odom` (pose + velocity,
  `nav_msgs/Odometry`), `/bumper` (contact sensor, `ros_gz_interfaces/Contacts`), `/tf`
- **`/odom` is wheel odometry (dead-reckoned):** it drifts when the wheels slip, so a robot
  stalled against something keeps reporting an advancing position even though it isn't
  moving. If `final_x`/`distance_travelled` look impossibly large, the robot is stuck —
  cross-check `contact_count`/`no_contact`.
- **For exact geometry, run `robotbase describe`** — it reports the robot's dimensions and
  joints, the world's models and arena bounds, and every scenario's assertions, as
  structured data read straight from the project files (so it can't drift, unlike numbers
  restated in prose). The starting pose is whatever the scenario's `setup.robot.pose` says.

You do **not** need to rebuild after editing the controller (the workspace is symlink-
installed); just run the scenario again. `robotbase build` is harmless if you prefer.

## Inspecting a failed run

Start with **`robotbase diagnose`** — it explains *why* the last run failed in plain
language (which assertions failed, the collision / closest-approach from the episode, and
whether the controller was still driving into the obstacle). For deeper inspection, every
run is recorded to an MCAP episode you can interrogate:

    robotbase diagnose                   # plain-language "why" for the latest failed run
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
