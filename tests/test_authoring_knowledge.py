"""The knowledge layer: strict schemas that name a bad key, and a GENERAL (schema-derived, not
task-specific) authoring reference shipped in the WITH scaffold's AGENTS.md."""
import pytest

from robotbase.robotspec.schema import RobotSpec, RobotSpecError
from robotbase.robotspec.schema_docs import authoring_json_schema, authoring_reference
from robotbase.worldspec.schema import WorldSpec, WorldSpecError


def test_world_schema_rejects_unknown_obstacle_keys():
    # The exact wrong guess the pilot agent made: {type, pose} instead of {shape, at}.
    bad = {"obstacles": [{"id": "b", "type": "box", "pose": [2, 0, 0.25], "size": [0.5, 0.5, 0.5]}]}
    with pytest.raises(Exception) as e:
        WorldSpec.model_validate(bad)
    assert "pose" in str(e.value)


def test_bad_shape_size_gives_clean_error_not_crash():
    # A wrong-length size must not crash the URDF renderer with a bare unpack error (which made the
    # WITH agent flail on opaque tracebacks) — it must name the problem.
    from robotbase.robotspec.ir import ShapeSizeError
    from robotbase.robotspec.semantic import geometry_from_spec
    with pytest.raises(ShapeSizeError) as e:
        geometry_from_spec("box", [0.35, 0.30, 0.15, 0.1])   # 4 values
    assert "box" in str(e.value) and "3 value" in str(e.value)
    with pytest.raises(ShapeSizeError):
        geometry_from_spec("cylinder", [0.02])               # cylinder needs 2


def test_robot_schema_rejects_unknown_sensor_keys():
    bad = {"base": "differential-drive", "sensors": [{"type": "lidar", "enabled": True}]}
    with pytest.raises(Exception) as e:
        RobotSpec.model_validate(bad)
    assert "enabled" in str(e.value)


def test_authoring_reference_is_general_not_task_specific():
    ref = authoring_reference().lower()
    # documents the FORMAT / vocabulary (applies to any task)
    for token in ("robot.yaml", "world.yaml", "differential-drive", "lidar", "camera",
                  "shape", "at:", "obstacles", "walls", "base"):
        assert token in ref, f"reference missing general token {token!r}"
    # does NOT leak any benchmark task's answer
    for leak in ("diff-lidar-world", "sensor-on-mast", "two-sensor", "add-sensor",
                 "(2, 0)", "2 0 0.25", "stop_at_1m", "1.37"):
        assert leak not in ref, f"reference leaks task-specific detail {leak!r}"


def test_authoring_json_schema_is_valid_and_complete():
    js = authoring_json_schema()
    assert set(js) == {"robot.yaml", "world.yaml"}
    robot_props = js["robot.yaml"]["properties"]
    assert {"base", "body", "sensors", "parts"} <= set(robot_props)
    assert "obstacles" in js["world.yaml"]["properties"]


def test_reference_covers_compiler_vocabulary_no_drift():
    # The knowledge layer is schema-derived: it must always reflect the compiler's real registries,
    # so adding a shape/archetype/sensor can't leave the docs silently stale.
    from robotbase.robotspec.ir import SHAPE_SIZE
    from robotbase.robotspec.modules import MODULES
    from robotbase.robotspec.sensors import SENSORS
    ref = authoring_reference()
    for shape in SHAPE_SIZE:
        assert shape in ref, f"reference missing shape {shape!r}"
    for arch in MODULES:
        assert arch in ref, f"reference missing archetype {arch!r}"
    for sensor in SENSORS:
        assert sensor in ref, f"reference missing sensor {sensor!r}"


def test_with_scaffold_agents_md_is_authoring_oriented(tmp_path):
    from robotbase.robotbench.scaffolds import build_scaffold
    d = build_scaffold({"id": "author/x", "kind": "author", "prompt": "Build a robot."},
                       "with", str(tmp_path))
    agents = open(f"{d}/AGENTS.md", encoding="utf-8").read().lower()
    assert "robot.yaml" in agents and "world.yaml" in agents and "author" in agents
    assert "implement the robot's controller" not in agents   # not the v1 fix-a-controller doc
