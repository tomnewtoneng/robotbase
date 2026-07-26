"""The two experiment arms: identical task, identical sim — only the tool layer differs.
See docs/design/robotbench-validation.md."""
from __future__ import annotations


def build_task_prompt(task: dict) -> str:
    return (
        f"You are solving the robotics scenario '{task['scenario']}' "
        f"(skill: {task['skill']}) on a {task['robot']} robot.\n"
        "The starter controller is deliberately incomplete and fails the scenario. Make the "
        "robot satisfy the scenario. Rules:\n"
        "- Only edit the controller source file; do not change anything else.\n"
        "- Do not claim success until you have verified the robot's behaviour yourself.\n"
        "- When you are finished, stop.\n"
    )


def without_orientation(project_dir: str, task: dict) -> str:
    # The raw-but-competent ROS 2 baseline: what a ROS dev already knows, minus robotbase's verbs.
    return (
        "\nYou have a bash shell in the project directory and the same running Gazebo sim. "
        "You do NOT have the robotbase test/diagnose/episode/describe tools. To work:\n"
        "- Launch/inspect the sim with raw ROS 2 + Gazebo (`ros2 launch ...`, `ros2 topic list`, "
        "`ros2 topic echo <topic>`, `gz` commands).\n"
        "- The controller you may edit is the Python node under `src/<pkg>/<pkg>/controller.py`.\n"
        "- The robot publishes/subscribes topics you can discover with `ros2 topic list`.\n"
    )


def arm_context(arm: str, project_dir: str, task: dict) -> dict:
    prompt = build_task_prompt(task)
    if arm == "with":
        return {"prompt": prompt, "tools": ["robotbase-mcp"], "docs": ["AGENTS.md"]}
    if arm == "without":
        return {"prompt": prompt + without_orientation(project_dir, task),
                "tools": ["bash"], "docs": []}
    raise ValueError(f"unknown arm {arm!r}; expected 'with' or 'without'")
