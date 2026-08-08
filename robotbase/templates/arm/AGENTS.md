# Robotbase Project Instructions

This is a Robotbase **fixed-base 2-DOF arm** project — a ROS 2 Jazzy + Gazebo Harmonic stack that
runs headless in Docker. You build and verify robots *declaratively*: everything here is yours to
change — the arm and its sensors (`robot.yaml`), the world (`world.yaml`), the control config
(the joint controllers' PID gains under `control:`), and the test scenarios — plus the control logic
you implement. You edit, compile, and run, verifying by the structured result, never by inspection.

This project ships a working arm, one **smoke-test scenario** (`reach-configuration`), and a
**minimal working controller** that commands a fixed configuration and passes it. Everything here
is yours to change. Run
`robotbase describe` for ground truth (joints, limits, controller gains) and `robotbase schema` for
the full authoring format (robot / world / **scenario**). When a task is about a specific scenario,
**read its YAML first** for the target and tolerance.

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

The starter controller (`src/warehouse_bot/warehouse_bot/controller.py`) commands a fixed
configuration (shoulder = 1.0, elbow = -1.4) and holds it — enough to pass `reach-configuration`.
Rewrite it to command the target configuration your task asks for, and keep publishing so the
controllers hold the pose while it settles.

You do **not** need to rebuild after editing the controller (symlink-installed); just run the
scenario again.

**Controller config vs. algorithm.** The joint position controllers' PID gains are compiled from
the spec — tune them declaratively in `robot.yaml` under
`control: {joints: {shoulder_joint: {p, i, d}, elbow_joint: {p, i, d}}}` (e.g. if the arm droops or
oscillates). The control *algorithm* — deciding what target to command — stays yours in
`controller.py`. See `robotbase describe` / the authoring reference for the `control:` schema.

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
