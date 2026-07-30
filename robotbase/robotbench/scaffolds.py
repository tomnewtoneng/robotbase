"""Per-arm, per-kind scaffold builders for the RobotBench v2 authoring suite.

Both arms are handed the *same* task and the *same* provided controller (byte-identical); only
the authoring surface differs:

- **WITH**  → a real, `robotbase up`-able project **named `robot`** (so the Gazebo model spawns as
  `robot`, per the interface contract), with `robot.yaml`/`world.yaml` reset to minimal authoring
  stubs so the agent builds the robot + world from scratch, plus the controller under
  `controllers/` and `TASK.md`.
- **WITHOUT** → an empty colcon workspace: `src/authored_pkg/` with `package.xml`, `setup.py`,
  and empty `urdf/ worlds/ launch/`, the controller under `authored_pkg/controllers/`,
  `RAW-ROS-ORIENTATION.md` (env-only, no templates), and `TASK.md`.

Both start from an equivalently *empty* robot: the WITH stub carries only `base:
differential-drive` (the prompt already names a differential-drive robot) — sensors, mounts, and
the world are the agent's job. `kind == "import"` tasks additionally drop `vendor_bot.urdf` at the
scaffold root. The scaffold is written under a caller-provided scratch dir, never inside the repo.
"""
from __future__ import annotations

import os
import shutil

from robotbase.generator import create_project, template_dir

_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
_CONTROLLER = os.path.join(_FIXTURES, "controllers", "stop_at_1m.py")
_ORIENTATION = os.path.join(_FIXTURES, "RAW-ROS-ORIENTATION.md")
_VENDOR_URDF = os.path.join(_FIXTURES, "vendor_bot.urdf")

# The agent authors from here: a bare differential-drive base (named in the prompt), no sensors,
# an empty ground world. Everything the task actually tests — sensors, mounts, obstacles — is TODO.
_STUB_ROBOT = "version: 1\nname: robot\nbase: differential-drive\n"
_STUB_WORLD = "version: 1\nname: warehouse\nground: true\nlight: sun\n"


def build_scaffold(task: dict, arm: str, dest_root: str) -> str:
    """Materialise the starting scaffold for `task` on `arm` under `dest_root`; return its dir."""
    os.makedirs(dest_root, exist_ok=True)
    if arm == "with":
        dest = _build_with(dest_root)
    elif arm == "without":
        dest = os.path.join(dest_root, "without")
        os.makedirs(dest, exist_ok=True)
        _build_without(dest)
    else:
        raise ValueError(f"unknown arm {arm!r}; expected 'with' or 'without'")

    with open(os.path.join(dest, "TASK.md"), "w", encoding="utf-8") as f:
        f.write(task["prompt"])
    if task.get("kind") == "import":
        shutil.copyfile(_VENDOR_URDF, os.path.join(dest, "vendor_bot.urdf"))
    return dest


def _build_with(dest_root: str) -> str:
    """A real Robotbase project named `robot` with its specs reset to authoring stubs."""
    proj = create_project("robot", dest_root, template_dir("differential-drive"))
    with open(os.path.join(proj, "robot.yaml"), "w", encoding="utf-8") as f:
        f.write(_STUB_ROBOT)
    with open(os.path.join(proj, "world.yaml"), "w", encoding="utf-8") as f:
        f.write(_STUB_WORLD)
    controllers = os.path.join(proj, "controllers")
    os.makedirs(controllers, exist_ok=True)
    shutil.copyfile(_CONTROLLER, os.path.join(controllers, "stop_at_1m.py"))
    # Replace the template's fix-a-controller AGENTS.md with the authoring knowledge layer: a
    # general, schema-derived format reference (never task-specific) + the tool workflow.
    with open(os.path.join(proj, "AGENTS.md"), "w", encoding="utf-8") as f:
        f.write(_with_agents_md())
    return proj


def _with_agents_md() -> str:
    from robotbase.robotspec.schema_docs import authoring_reference
    return (
        "# Robotbase Project Instructions\n\n"
        "This is a ROS 2 Jazzy + Gazebo Harmonic project that runs headless in Docker. Your job is\n"
        "to AUTHOR the robot and world described in `TASK.md` by editing the declarative specs\n"
        "`robot.yaml` and `world.yaml`, then compiling and verifying them. You do not operate\n"
        "Gazebo directly — use the `robotbase` MCP tools:\n\n"
        "- `workspace_build` — recompile robot.yaml/world.yaml to URDF/SDF and build (run after edits).\n"
        "- `simulation_launch` / `simulation_stop` / `simulation_reset` — run the headless sim.\n"
        "- `ros_list_topics` / `ros_inspect_topic` — inspect the live ROS graph to VERIFY behaviour.\n"
        "- `project_describe` — structured ground truth about the compiled robot/world.\n"
        "- `environment_doctor` — diagnose infrastructure problems if build/launch fail.\n\n"
        "This is an AUTHORING task: there is no scenario to run and no controller to fix, so you do\n"
        "not need `scenario_run`, the `episode_*` tools, or `diagnose_run`. Verify by launching and\n"
        "checking topics: the robot spawns as model `robot`, `/scan` publishes, and `/cmd_vel` moves\n"
        "it. When `workspace_build` reports an error, read it — it names the exact problem (an unknown\n"
        "key, a missing link, a wrong-length size) — and fix that; do not thrash.\n\n"
        "A working controller is already provided under `controllers/` — do NOT edit it; your job\n"
        "is only the robot and the world it runs against. Do not claim success until you have\n"
        "launched the sim and confirmed the robot's behaviour from the running system.\n\n"
        + authoring_reference()
    )


def _build_without(dest: str) -> None:
    pkg = os.path.join(dest, "src", "authored_pkg")
    for sub in ("urdf", "worlds", "launch", "controllers"):
        os.makedirs(os.path.join(pkg, sub), exist_ok=True)
    shutil.copyfile(_CONTROLLER, os.path.join(pkg, "controllers", "stop_at_1m.py"))
    shutil.copyfile(_ORIENTATION, os.path.join(dest, "RAW-ROS-ORIENTATION.md"))
    # The raw-ROS arm still needs the same headless ROS 2 + Gazebo container (the environment is
    # not the thing under test — the authoring surface is). Reuse the shared runtime image; no
    # robotbase CLI conveniences. The agent drives colcon/ros2/gz itself via `docker compose exec`.
    with open(os.path.join(dest, "compose.yaml"), "w", encoding="utf-8") as f:
        f.write(
            "services:\n"
            "  ros:\n"
            "    image: robotbase-runtime:latest\n"
            "    working_dir: /workspace\n"
            "    volumes:\n"
            "      - ./:/workspace\n"
            "    environment:\n"
            "      - LIBGL_ALWAYS_SOFTWARE=1\n"
            "      - OGRE_RTT_MODE=Copy\n"
            "    command: sleep infinity\n"
        )
    # A COHERENT empty ament_cmake package: it builds as-is and installs launch/urdf/worlds to
    # share/ so `ros2 launch authored_pkg <file>` resolves. The agent's job is to author the
    # contents (URDF, world SDF, bring-up launch) — not to repair a broken skeleton.
    with open(os.path.join(pkg, "package.xml"), "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0"?>\n'
            '<package format="3">\n'
            "  <name>authored_pkg</name>\n"
            "  <version>0.0.0</version>\n"
            "  <description>RobotBench authored package (raw ROS 2 arm).</description>\n"
            "  <maintainer email=\"robotbench@example.com\">robotbench</maintainer>\n"
            "  <license>MIT</license>\n"
            "  <buildtool_depend>ament_cmake</buildtool_depend>\n"
            "  <exec_depend>ros_gz_sim</exec_depend>\n"
            "  <exec_depend>ros_gz_bridge</exec_depend>\n"
            "  <exec_depend>robot_state_publisher</exec_depend>\n"
            "  <exec_depend>xacro</exec_depend>\n"
            "  <export><build_type>ament_cmake</build_type></export>\n"
            "</package>\n"
        )
    with open(os.path.join(pkg, "CMakeLists.txt"), "w", encoding="utf-8") as f:
        f.write(
            "cmake_minimum_required(VERSION 3.8)\n"
            "project(authored_pkg)\n"
            "find_package(ament_cmake REQUIRED)\n"
            "# Install whatever the agent authors so `ros2 launch authored_pkg <file>` can find it.\n"
            "install(DIRECTORY launch urdf worlds DESTINATION share/${PROJECT_NAME})\n"
            "ament_package()\n"
        )
