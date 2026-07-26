import yaml
from importlib import resources
from robotbase.bench import TASKS


def _scenario_path(task):
    root = resources.files("robotbase") / "templates" / task["template"]
    return root / "simulation" / "scenarios" / f"{task['scenario']}.yaml"


def test_every_benchmark_scenario_has_a_randomize_block():
    for task in TASKS:
        data = yaml.safe_load(_scenario_path(task).read_text())
        assert data.get("randomize"), f"{task['id']} scenario is missing a randomize block"
