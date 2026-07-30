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


def build_author_prompt(task: dict, arm: str) -> str:
    """The v2 authoring prompt: the task text verbatim + rules identical across arms, the
    interface contract, and the arm's own bring-up command. Fairness depends on the task text,
    the rules, and the contract being byte-for-byte the same for both arms — only the final
    bring-up line differs (it names each arm's tooling)."""
    bringup = ("robotbase up" if arm == "with"
               else "ros2 launch authored_pkg bringup.launch.py")
    return (
        f"{task['prompt']}\n\n"
        "Rules:\n"
        "- Before authoring, read the documentation files in this project (e.g. the project's "
        "instructions / orientation) for the exact format and conventions.\n"
        "- Author the robot, the world, the package, and the launch yourself.\n"
        "- A working controller is already provided (the `stop_at_1m` node) — do NOT modify the "
        "provided controller. Your job is only to build the robot and world it must run against.\n"
        "- Do not claim success until you have brought the simulation up yourself and verified the "
        "robot's behaviour from the running system — not by reading source.\n"
        "- When you are finished, stop.\n\n"
        f"Interface contract: the robot must spawn under model name `{task['model_name']}`, "
        "subscribe to /cmd_vel (geometry_msgs/Twist) and drive from it, and publish /scan "
        "(sensor_msgs/LaserScan) from a forward-facing sensor.\n"
        f"Bring the project up with: {bringup}\n"
    )


def arm_context(arm: str, project_dir: str, task: dict) -> dict:
    if arm not in ("with", "without"):
        raise ValueError(f"unknown arm {arm!r}; expected 'with' or 'without'")

    # v2 authoring/import tasks: identical authoring prompt, arm-specific tools + docs.
    if task.get("kind") in {"author", "import"}:
        prompt = build_author_prompt(task, arm)
        if arm == "with":
            return {"prompt": prompt, "tools": ["robotbase-mcp"], "docs": ["AGENTS.md"]}
        return {"prompt": prompt, "tools": ["bash", "read", "edit", "write"],
                "docs": ["RAW-ROS-ORIENTATION.md"]}

    # Legacy v1 fix-a-controller tasks (kept for backward-compat tests).
    prompt = build_task_prompt(task)
    if arm == "with":
        return {"prompt": prompt, "tools": ["robotbase-mcp"], "docs": ["AGENTS.md"]}
    return {"prompt": prompt + without_orientation(project_dir, task),
            "tools": ["bash"], "docs": []}
