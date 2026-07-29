"""Real dependencies for the RobotBench runner: generate a project, start its sim, judge it —
by shelling to the robotbase CLI. Plus the task/arm expanders. See design/robotbench-validation.md."""
from __future__ import annotations

import os
import subprocess
import time
import uuid

from robotbase.bench import TASKS
from robotbase.generator import create_project, template_dir
from robotbase.robotbench.author_judge import author_judge
from robotbase.robotbench.gz_probe import cmd_vel_is_live, sample_model_pose
from robotbase.robotbench.judge import judge
from robotbase.robotbench.scaffolds import build_scaffold


def expand_arms(arm: str) -> list[str]:
    return ["with", "without"] if arm == "both" else [arm]


def expand_tasks(task: str) -> list[dict]:
    if task == "all":
        return list(TASKS)
    hits = [t for t in TASKS if t["id"] == task]
    if not hits:
        raise ValueError(f"unknown task {task!r}; known: {[t['id'] for t in TASKS]}")
    return hits


def real_generate(workdir: str):
    """Factory: returns a generate(task, trial) -> project_dir that creates a fresh project."""
    def generate(task: dict, trial: int) -> str:
        name = f"rbench-{task['scenario']}-{trial}-{uuid.uuid4().hex[:6]}"
        return create_project(name, workdir, template_dir(task["template"]))
    return generate


def real_start_sim(project_dir: str) -> None:
    subprocess.run(["robotbase", "up"], cwd=project_dir, check=True)


def real_teardown(project_dir: str) -> None:
    subprocess.run(["robotbase", "down"], cwd=project_dir)   # no check — down may warn if already down


def real_judge(trials: int):
    """Factory: returns a judge_fn(project_dir, scenario, seed) using the external judge."""
    def judge_fn(project_dir: str, scenario: str, seed: int) -> dict:
        return judge(project_dir, scenario, trials=trials, seed=seed)
    return judge_fn


# ---- v2 authoring deps ------------------------------------------------------
# Real bring-up shells into each arm's Gazebo container. The exact container mechanics (compose
# service, spawn-pose override) are tuned against the live sim in Task 9's calibration; the
# offline layer (author_judge orchestration, acceptance predicates) is what's unit-tested.

_SETUP = "source /opt/ros/jazzy/setup.bash; source install/setup.bash 2>/dev/null; "
_WORLD = "warehouse"


def _sh(project_dir: str):
    """An sh(cmd) -> stdout that execs inside the project's ROS container (the gz_probe seam)."""
    def sh(cmd: str, timeout: float = 60.0) -> str:
        r = subprocess.run(
            ["docker", "compose", "exec", "-T", "ros", "bash", "-lc", _SETUP + cmd],
            cwd=project_dir, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    return sh


def author_generate(workdir: str, arm: str):
    """Factory: returns generate(task, trial) -> scaffold dir for `arm` under a fresh subdir."""
    def generate(task: dict, trial: int) -> str:
        root = os.path.join(workdir, f"{task['id'].replace('/', '_')}-{arm}-{trial}-{uuid.uuid4().hex[:6]}")
        return build_scaffold(task, arm, root)
    return generate


def _spawn_robot(sh, model: str, pose) -> None:
    # ros_gz_sim create ignores SDF <pose>; the seeded spawn pose is set with -x/-y/-z.
    x, y, z = pose
    sh(f"ros2 run ros_gz_sim create -world {_WORLD} -name {model} "
       f"-x {x} -y {y} -z {z} -topic robot_description", timeout=45)


def real_bringup_with(project_dir: str, pose):
    """WITH arm: `robotbase up` recompiles robot.yaml/world.yaml and starts the container + sim.
    Returns a teardown callable (`robotbase down`)."""
    subprocess.run(["robotbase", "up"], cwd=project_dir, check=True, timeout=1800)
    subprocess.run(["robotbase", "launch"], cwd=project_dir, check=True, timeout=300)
    return lambda: subprocess.run(["robotbase", "down"], cwd=project_dir, timeout=120)


def real_bringup_without(project_dir: str, pose):
    """WITHOUT arm: build the colcon workspace and `ros2 launch` the authored bring-up in the
    same headless Gazebo container. Returns a teardown callable (kill launch + `robotbase down`)."""
    sh = _sh(project_dir)
    subprocess.run(["robotbase", "up"], cwd=project_dir, check=True, timeout=1800)
    sh("colcon build", timeout=1200)
    proc = subprocess.Popen(
        ["docker", "compose", "exec", "-T", "ros", "bash", "-lc",
         _SETUP + "ros2 launch authored_pkg bringup.launch.py"],
        cwd=project_dir)
    time.sleep(15)  # let the launch spawn the robot + world before the judge probes

    def teardown():
        sh("pkill -f 'ros2 launch' ; pkill -f ros_gz_sim ; true", timeout=20)
        proc.terminate()
        subprocess.run(["robotbase", "down"], cwd=project_dir, timeout=120)
    return teardown


def real_run_controller(project_dir: str, duration_s: float) -> None:
    """Run the provided (immutable) stop_at_1m controller against the live sim for `duration_s`."""
    sh = _sh(project_dir)
    ctrl = "$(find . -name stop_at_1m.py | head -1)"
    sh(f"timeout {int(duration_s)} python3 {ctrl} ; true", timeout=duration_s + 15)


def real_author_judge(arm: str, trials: int = 3, evidence_root: str | None = None):
    """Factory: returns judge_fn(project, scenario, seed) that runs the behavioral author judge
    with the arm's real bring-up and the real ground-truth probe."""
    bringup = real_bringup_with if arm == "with" else real_bringup_without

    def judge_fn(project_dir: str, scenario: str, seed: int) -> dict:
        sh = _sh(project_dir)
        task = {"judge_scenario": scenario, "model_name": "robot"}
        evidence_dir = (os.path.join(evidence_root, f"{arm}-{scenario}")
                        if evidence_root else None)
        return author_judge(
            project_dir, task,
            bringup_fn=bringup,
            run_controller_fn=real_run_controller,
            sample_fn=lambda m, d, hz=10: sample_model_pose(m, d, sh, world=_WORLD, hz=hz),
            liveness_fn=lambda need, t: cmd_vel_is_live(sh, need, world=_WORLD),
            evidence_dir=evidence_dir, trials=trials, seed=seed)
    return judge_fn
