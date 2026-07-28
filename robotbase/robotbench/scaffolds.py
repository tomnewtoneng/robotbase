"""Per-arm, per-kind scaffold builders for the RobotBench v2 authoring suite.

Both arms are handed the *same* task and the *same* provided controller (byte-identical); only
the authoring surface differs:

- **WITH**  → an empty Robotbase project: a `robotbase.yaml` manifest, empty `robots/` and
  `worlds/` for the agent to author into, the controller under `controllers/`, and `TASK.md`.
- **WITHOUT** → an empty colcon workspace: `src/authored_pkg/` with `package.xml`, `setup.py`,
  and empty `urdf/ worlds/ launch/`, the controller under `authored_pkg/controllers/`,
  `RAW-ROS-ORIENTATION.md` (env-only, no templates), and `TASK.md`.

`kind == "import"` tasks additionally drop `vendor_bot.urdf` at the scaffold root for both arms.
The scaffold is written under a caller-provided scratch dir, never inside the repo tree.
"""
from __future__ import annotations

import os
import shutil

_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
_CONTROLLER = os.path.join(_FIXTURES, "controllers", "stop_at_1m.py")
_ORIENTATION = os.path.join(_FIXTURES, "RAW-ROS-ORIENTATION.md")
_VENDOR_URDF = os.path.join(_FIXTURES, "vendor_bot.urdf")


def build_scaffold(task: dict, arm: str, dest_root: str) -> str:
    """Materialise the starting scaffold for `task` on `arm` under `dest_root`; return its dir."""
    dest = os.path.join(dest_root, arm)
    os.makedirs(dest, exist_ok=True)
    if arm == "with":
        _build_with(dest)
    elif arm == "without":
        _build_without(dest)
    else:
        raise ValueError(f"unknown arm {arm!r}; expected 'with' or 'without'")

    with open(os.path.join(dest, "TASK.md"), "w", encoding="utf-8") as f:
        f.write(task["prompt"])
    if task.get("kind") == "import":
        shutil.copyfile(_VENDOR_URDF, os.path.join(dest, "vendor_bot.urdf"))
    return dest


def _build_with(dest: str) -> None:
    os.makedirs(os.path.join(dest, "robots"), exist_ok=True)
    os.makedirs(os.path.join(dest, "worlds"), exist_ok=True)
    controllers = os.path.join(dest, "controllers")
    os.makedirs(controllers, exist_ok=True)
    shutil.copyfile(_CONTROLLER, os.path.join(controllers, "stop_at_1m.py"))
    with open(os.path.join(dest, "robotbase.yaml"), "w", encoding="utf-8") as f:
        f.write(
            "# Robotbase project manifest — empty authoring scaffold.\n"
            "# Author robot.yaml/world.yaml (via the robotbase tools); `robotbase up` compiles + runs.\n"
            "launch_package: robot_bringup\n"
            "launch_file: simulation.launch.py\n"
            "world_name: warehouse\n"
            "robot_name: robot\n"
            "ready_topics: [/scan]\n"
        )


def _build_without(dest: str) -> None:
    pkg = os.path.join(dest, "src", "authored_pkg")
    for sub in ("urdf", "worlds", "launch", "controllers"):
        os.makedirs(os.path.join(pkg, sub), exist_ok=True)
    shutil.copyfile(_CONTROLLER, os.path.join(pkg, "controllers", "stop_at_1m.py"))
    shutil.copyfile(_ORIENTATION, os.path.join(dest, "RAW-ROS-ORIENTATION.md"))
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
            "  <export><build_type>ament_python</build_type></export>\n"
            "</package>\n"
        )
    with open(os.path.join(pkg, "setup.py"), "w", encoding="utf-8") as f:
        f.write(
            "from setuptools import setup\n\n"
            "package_name = 'authored_pkg'\n\n"
            "setup(\n"
            "    name=package_name,\n"
            "    version='0.0.0',\n"
            "    packages=[package_name],\n"
            "    data_files=[\n"
            "        ('share/ament_index/resource_index/packages',\n"
            "         ['resource/' + package_name]),\n"
            "        ('share/' + package_name, ['package.xml']),\n"
            "    ],\n"
            "    install_requires=['setuptools'],\n"
            "    zip_safe=True,\n"
            "    maintainer='robotbench',\n"
            "    license='MIT',\n"
            "    entry_points={},\n"
            ")\n"
        )
