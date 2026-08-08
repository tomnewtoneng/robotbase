# Robotbase Project Instructions

This is a Robotbase **differential-drive robot** project — a ROS 2 Jazzy + Gazebo Harmonic stack
that runs headless in Docker. You build and verify robots *declaratively*: everything here is yours
to change — the robot and its sensors (`robot.yaml`), the world (`world.yaml`), the control config,
and the test scenarios — plus the control logic you implement. You edit, compile, and run, verifying
by the structured result, never by inspection.

This project ships a working differential-drive robot with a LiDAR, a set of scenarios, and a
**starter controller you implement** for the behaviour you want. Run `robotbase describe` for ground
truth and `robotbase schema` for the full authoring format (robot / world / **scenario**). When a
task is about a specific scenario, **read its YAML first** — it declares exactly what it checks; don't
assume the task from file names.

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

Your control *algorithm* lives in `controller.py` (below) — that's always yours to write. The drive
controller's *config* is declarative: `robot.yaml`'s `control: {base: {odom_publish_frequency, ...}}`
tunes it, and wheel geometry stays in `drive:` (you rarely need this).

The starter controller (`src/mobile_nav/mobile_nav/controller.py`) just
drives straight forward and ignores its sensors — so it fails every scenario. Rewrite it to
satisfy whichever scenario you're working on. Read that scenario's assertions to see exactly
what "pass" means (e.g. `robot_reached_pose` wants a final position near a target;
`no_contact`/`no_collision` want you not to hit anything).

- Robot type: differential drive
- Key topics: `/cmd_vel` (velocity command out, `geometry_msgs/Twist`: `linear.x` forward,
  `angular.z` turn), `/scan` (LiDAR, `sensor_msgs/LaserScan`), `/odom` (pose + velocity,
  `nav_msgs/Odometry`), `/bumper` (contact sensor, `ros_gz_interfaces/Contacts` — fires on a
  real collision), `/tf`
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
