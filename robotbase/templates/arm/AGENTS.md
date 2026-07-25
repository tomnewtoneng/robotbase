# Robotbase Project Instructions

This is a ROS 2 Jazzy + Gazebo Harmonic **fixed-base 2-DOF arm** project that runs headless
in Docker. Your job is to implement the arm's controller so that the **simulation scenario
you're asked to satisfy passes** — verified by running it, not by inspection. Read the
scenario's YAML first to learn its target and tolerance.

## Environment

The simulation runs inside a Docker container. You do **not** operate Gazebo directly. Use
the Robotbase tools — the `robotbase` CLI below, or the equivalent MCP tools — to build, run
scenarios, and read structured results.

## Commands (run from this directory)

    robotbase describe              # robot facts (joints + limits, command topics), world, scenarios
    robotbase build                 # build the workspace
    robotbase test <scenario-name>  # run a scenario (exit 0 = pass, 1 = fail; JSON result)
    robotbase test --list           # list scenarios

Available scenarios (each `.yaml` in `simulation/scenarios/` defines its target and
assertions — read the one you're solving):

- `reach-configuration` — move the joints to a target configuration (angles in radians) and
  hold there within tolerance.

## The controller

The arm has two revolute joints, **shoulder** and **elbow**, both pitching in the x-z plane.
Command each joint's target angle (radians) by publishing `std_msgs/Float64` on
`/shoulder_cmd` and `/elbow_cmd`; a position controller drives the joint there and holds it.
Read the current angles from `/joint_states` (`sensor_msgs/JointState`; the `name`/`position`
arrays include `shoulder_joint` and `elbow_joint`).

The starter controller (`src/warehouse_bot/warehouse_bot/controller.py`) sets up the
publishers but **never commands a target**, so the arm droops/holds the wrong pose and fails.
Rewrite it to command the target configuration the scenario asks for, and keep publishing so
the controllers hold the pose while it settles.

You do **not** need to rebuild after editing the controller (symlink-installed); just run the
scenario again.

## Inspecting a run

Start with **`robotbase diagnose`** — it explains why the last run failed in plain language
(the failed assertion and the per-joint error). Every run is also recorded to an MCAP
episode you can interrogate:

    robotbase diagnose                               # plain-language "why" for the latest run
    robotbase episode summary                        # topics, counts, duration
    robotbase episode query --topic /joint_states    # joint angles over the run

(`episode summary`/`query` print JSON on stdout and a hint on stderr — capture stdout alone,
e.g. `2>/dev/null`, when parsing.)

## Requirements — do not claim success without evidence

1. Run the scenario with `robotbase test <name>` and read the `joint_positions` metric and
   the assertion result (its `detail` lists the per-joint error).
2. Check `joint_velocities` — near-zero means the arm has settled and is holding the pose;
   large values mean it was still moving at capture (command it earlier / hold longer).
3. Iterate on the controller until the scenario passes (exit 0, all assertions true).
4. Report the final metrics.

Do **not** claim success based only on reading source code — the scenario must actually pass.
Prefer Robotbase tools over raw ROS/Gazebo commands.
