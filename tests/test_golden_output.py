"""Golden-output guard for the P4 semantic-IR refactor: the compiled URDF/SDF for every shipped
template + reference solution is frozen here, so any refactor that changes a single byte fails
loudly. Regenerate intentionally with UPDATE_GOLDEN=1 (only when a change is meant to alter output)."""
import glob
import os
import pathlib

import pytest

from robotbase.generator import template_dir
from robotbase.robotspec.compile import compile_robot
from robotbase.robotspec.schema import RobotSpec
from robotbase.worldspec.compile import compile_world
from robotbase.worldspec.schema import WorldSpec

GOLDEN = pathlib.Path(__file__).parent / "golden"
REF = pathlib.Path(__file__).parent.parent / "robotbase" / "robotbench" / "fixtures" / "reference"


def _cases():
    cases = []
    for name in ["differential-drive", "camera-bot", "arm", "drone"]:
        d = pathlib.Path(template_dir(name))
        r, w = d / "robot.yaml", d / "world.yaml"
        if r.exists():
            cases.append((f"tpl-{name}", str(r), str(w) if w.exists() else None))
    for d in sorted(glob.glob(str(REF / "*"))):
        r, w = os.path.join(d, "robot.yaml"), os.path.join(d, "world.yaml")
        if os.path.exists(r):
            cases.append((f"ref-{os.path.basename(d)}", r, w if os.path.exists(w) else None))
    return cases


def _compile(robot_yaml, world_yaml):
    spec = RobotSpec.from_yaml(robot_yaml)
    for p in spec.parts:                       # resolve project-relative custom-import paths
        if p.use == "custom" and p.urdf and not os.path.isabs(p.urdf):
            p.urdf = os.path.join(os.path.dirname(robot_yaml), os.path.basename(p.urdf))
    urdf = compile_robot(spec).urdf
    sdf = compile_world(WorldSpec.from_yaml(world_yaml))[0] if world_yaml else ""
    return urdf, sdf


@pytest.mark.parametrize("name,robot_yaml,world_yaml", _cases(),
                         ids=[c[0] for c in _cases()])
def test_compiled_output_matches_golden(name, robot_yaml, world_yaml):
    urdf, sdf = _compile(robot_yaml, world_yaml)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        GOLDEN.mkdir(exist_ok=True)
        (GOLDEN / f"{name}.urdf").write_text(urdf, encoding="utf-8")
        (GOLDEN / f"{name}.sdf").write_text(sdf, encoding="utf-8")
        pytest.skip("updated golden")
    assert urdf == (GOLDEN / f"{name}.urdf").read_text(encoding="utf-8"), f"{name} URDF drifted"
    assert sdf == (GOLDEN / f"{name}.sdf").read_text(encoding="utf-8"), f"{name} SDF drifted"
