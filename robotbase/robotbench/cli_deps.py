"""Real dependencies for the RobotBench runner: generate a project, start its sim, judge it —
by shelling to the robotbase CLI. Plus the task/arm expanders. See design/robotbench-validation.md."""
from __future__ import annotations

import subprocess
import uuid

from robotbase.bench import TASKS
from robotbase.generator import create_project, template_dir
from robotbase.robotbench.judge import judge


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


def real_judge(trials: int):
    """Factory: returns a judge_fn(project_dir, scenario, seed) using the external judge."""
    def judge_fn(project_dir: str, scenario: str, seed: int) -> dict:
        return judge(project_dir, scenario, trials=trials, seed=seed)
    return judge_fn
