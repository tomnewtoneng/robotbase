from robotbase.bench import TASKS, BENCHMARK_VERSION
from robotbase.robotbench.records import BENCHMARK_VERSION as REC_VER

REQUIRED = {"id", "kind", "robot", "skill", "prompt", "model_name", "controller", "judge_scenario"}


def test_benchmark_version_is_2_everywhere():
    assert BENCHMARK_VERSION == 2 and REC_VER == 2


def test_suite_is_four_authoring_tasks():
    ids = [t["id"] for t in TASKS]
    assert ids == ["author/diff-lidar-world", "author/sensor-on-mast",
                   "author/two-sensor", "import/add-sensor"]
    assert {t["kind"] for t in TASKS} == {"author", "import"}


def test_every_task_has_required_keys_and_prompt():
    for t in TASKS:
        assert REQUIRED <= set(t), f"{t['id']} missing {REQUIRED - set(t)}"
        assert len(t["prompt"]) > 40 and t["model_name"] == "robot"
    imp = next(t for t in TASKS if t["kind"] == "import")
    assert imp["import_urdf"].endswith(".urdf")
