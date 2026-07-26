import pytest
from robotbase.robotspec.compile import UnknownArchetype, UnknownSensor, compile_robot
from robotbase.robotspec.schema import RobotSpec


def test_base_sugar_normalises_to_one_part():
    spec = RobotSpec(base="differential-drive")
    assert compile_robot(spec).manifest["control"]["velocity_topic"] == "/cmd_vel"


def test_parts_list_with_raw_part_and_sensor_on_it():
    spec = RobotSpec.model_validate({
        "name": "custom_bot",
        "parts": [
            {"use": "differential-drive"},
            {"links": [{"name": "mast", "shape": "cylinder", "size": [0.03, 0.5], "mass": 0.2}],
             "joints": [{"name": "mast_joint", "parent": "base_link", "child": "mast",
                         "type": "fixed", "xyz": [0, 0, 0.1]}]},
        ],
        "sensors": [{"type": "lidar", "on": "mast"}],
    })
    c = compile_robot(spec)
    assert "mast" in c.urdf and 'type="gpu_lidar"' in c.urdf
    assert '<child link="lidar_link"/>' in c.urdf     # the lidar joint exists
    assert "/scan" in c.manifest["ready_topics"]


def test_unknown_archetype_and_sensor_still_raise():
    with pytest.raises(UnknownArchetype):
        compile_robot(RobotSpec(base="hovercraft"))
    with pytest.raises(UnknownSensor):
        compile_robot(RobotSpec.model_validate(
            {"base": "differential-drive", "sensors": [{"type": "radar"}]}))
