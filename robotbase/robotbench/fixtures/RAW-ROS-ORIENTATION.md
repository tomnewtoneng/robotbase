# Raw ROS 2 Orientation

This is a raw ROS 2 workspace. You build a robot and a world from scratch with standard ROS 2
and Gazebo tools — there is no higher-level generator. This file tells you **only** how the
environment is wired and what "done" means. It deliberately contains **no** robot or world
authoring templates — designing the URDF/SDF and the launch is your job.

## Environment

- **Your shell runs on the host, but ROS 2 and Gazebo live inside a Docker container.** The
  workspace is bind-mounted into the container at `/workspace` (the container service is named
  `ros`). Edit files directly with your file tools, but run **every** `colcon`, `ros2`, and `gz`
  command *inside the container* via:

      docker compose exec -T ros bash -lc "source /opt/ros/jazzy/setup.bash; source install/setup.bash 2>/dev/null; <your command>"

  (The container is already up. Run `docker compose` from the project root.)
- **ROS 2 distro:** Jazzy Jalisco. **Simulator:** Gazebo Harmonic, **headless** (software
  rendering, `llvmpipe`) — inspect via topics and the `gz` CLI, not a viewport.
- **ROS ↔ Gazebo bridge:** `ros_gz_sim` and `ros_gz_bridge` are installed. Gazebo transports
  (`gz topic`) and ROS topics (`ros2 topic`) are separate namespaces; bridge the ones you need.

## Workspace layout

A colcon `ament_cmake` package `authored_pkg` is scaffolded for you under `src/authored_pkg/` with
empty `urdf/`, `worlds/`, and `launch/` dirs, a `package.xml`, and a `CMakeLists.txt` that already
installs those three dirs to the package share (so `ros2 launch authored_pkg <file>` resolves once
you `colcon build`). Put your robot description in `urdf/`, your world in `worlds/`, and your
bring-up in `launch/`. The provided controller lives at `authored_pkg/controllers/stop_at_1m.py` —
**do not modify it and do not run it yourself**: the harness runs it against your robot after
bring-up (the same for every submission). Your launch only needs to bring up the robot, the world,
and the ROS↔gz bridges — not the controller.

## Build & run

- Build: `colcon build` from the workspace root, then `source install/setup.bash`.
- Launch: `ros2 launch authored_pkg bringup.launch.py` — this is exactly what the judge runs.
- Inspect: `ros2 topic list`, `ros2 topic echo <topic>`, `ros2 topic hz <topic>`; `gz topic -l`,
  `gz topic -e -t <topic>` for Gazebo-side transports.

## Spawning into Gazebo

Spawn a model into a running Gazebo world with `ros_gz_sim create` (the `create` service /
node). **Important gotcha:** `ros_gz_sim create` **ignores** an SDF `<pose>` — set the spawn
position with the `-x`, `-y`, `-z` flags instead, or the model lands at the origin.

## The bring-up contract (what "done" means)

The judge brings your project up with `ros2 launch authored_pkg bringup.launch.py` and then runs
the provided controller. To pass, your launched system must:

- spawn the robot into Gazebo under the **model name `robot`**;
- **subscribe** `/cmd_vel` (`geometry_msgs/msg/Twist`) and actually drive from it;
- **publish** `/scan` (`sensor_msgs/msg/LaserScan`) from a forward-facing sensor (and, for a
  camera task, `/image`, `sensor_msgs/msg/Image`);
- come up within the world you were asked to build.

**You are finished** the moment your launch brings the sim up and you have confirmed, from the live
topics, that the robot spawns as model `robot`, `/scan` publishes, and `/cmd_vel` moves it. There
is nothing else to run — once those topics are healthy, stop and report success. Do not claim
success before you have confirmed them from the running system.
