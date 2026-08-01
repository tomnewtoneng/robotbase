"""Live calibration: each committed reference solution must be scored `solved` by the real judge.

This is the dogfooding gate — it proves every v2 task is actually solvable through the current
compiler AND that the behavioral judge is calibrated to real controller behaviour. It needs Docker
+ Gazebo, so it is skipped unless ROBOTBENCH_LIVE=1.

    ROBOTBENCH_LIVE=1 pytest tests/test_reference_solutions_live.py -v

Each case: build a WITH scaffold (a real robotbase project named `robot`), drop the reference
robot.yaml/world.yaml in, and run the real author judge (real bring-up + ground-truth pose probe).
"""
import os
import pathlib
import shutil

import pytest

from robotbase.robotbench.cli_deps import real_author_judge
from robotbase.robotbench.scaffolds import build_scaffold

pytestmark = pytest.mark.skipif(os.environ.get("ROBOTBENCH_LIVE") != "1",
                                reason="needs Docker sim (set ROBOTBENCH_LIVE=1)")

_REF = (pathlib.Path(__file__).resolve().parent.parent
        / "robotbase" / "robotbench" / "fixtures" / "reference")
_REFDIR = {
    "author/diff-lidar-world": "author-diff-lidar-world",
    "author/sensor-on-mast": "author-sensor-on-mast",
    "author/two-sensor": "author-two-sensor",
    "import/add-sensor": "import-add-sensor",
}
_SCENARIO = {
    "author/diff-lidar-world": "author_stop_at_1m",
    "author/sensor-on-mast": "author_mast_clear",
    "author/two-sensor": "author_two_sensor",
    "import/add-sensor": "author_stop_at_1m",
}


def _install(task_id: str, kind: str, dest: str) -> str:
    proj = build_scaffold({"id": task_id, "kind": kind, "prompt": "Reference calibration."},
                          "with", dest)
    refdir = _REF / _REFDIR[task_id]
    for spec in ("robot.yaml", "world.yaml"):
        src = refdir / spec
        if src.exists():
            shutil.copyfile(src, os.path.join(proj, spec))
    return proj


@pytest.mark.parametrize("task_id,kind", [
    ("author/diff-lidar-world", "author"),
    ("author/sensor-on-mast", "author"),
    ("author/two-sensor", "author"),
    ("import/add-sensor", "import"),
])
def test_reference_solution_is_solved_by_judge(task_id, kind, tmp_path):
    proj = _install(task_id, kind, str(tmp_path))
    # Seeded spawn jitter IS applied now (real_bringup_with teleports the robot to spawn_pose(seed)).
    # trials=1 keeps this calibration gate fast — it only needs to confirm the reference solves at the
    # first seed; the multi-seed robustness measure is exercised by the n-trial bench runs.
    jf = real_author_judge("with", trials=1, evidence_root=str(tmp_path / "ev"))
    out = jf(proj, _SCENARIO[task_id], seed=0)
    assert out["solved"] is True, f"{task_id} not solved by judge: {out}"
